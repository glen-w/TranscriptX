"""
Unified analysis pipeline orchestrator for TranscriptX.

This module provides a thin orchestration layer that coordinates
the DAG pipeline with preprocessing and output reporting.
"""

import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

# Suppress tokenizer warnings about parallelism to prevent console spam
def _ensure_tokenizers_parallelism() -> None:
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

from transcriptx.core.utils.logger import get_logger, log_pipeline_complete
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.dag_pipeline import create_dag_pipeline
from transcriptx.core.pipeline.preprocessing import validate_transcript
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.target_resolver import (
    AnalysisTargetRef,
    TranscriptRef,
    resolve_analysis_target,
)
from transcriptx.core.pipeline.output_reporter import (
    generate_comprehensive_output_summary,
    display_output_summary_to_user,
)
from transcriptx.core.pipeline.manifest_builder import write_output_manifest
from transcriptx.core.pipeline.module_registry import (
    get_available_modules as get_available_modules_from_registry,
    get_default_modules as get_default_modules_from_registry,
)
from transcriptx.core.utils.performance_logger import TimedJob
from transcriptx.core.utils.performance_estimator import (
    PerformanceEstimator,
    format_time_estimate,
)
from transcriptx.core.utils.paths import OUTPUTS_DIR, ensure_data_dirs
from transcriptx.core.utils.path_utils import (
    set_transcript_output_dir,
    clear_transcript_output_dir,
)
from transcriptx.core.utils.run_report import RunReport, save_run_report
from transcriptx.core.utils.run_manifest import (
    create_run_manifest,
    save_run_manifest,
    compute_file_hash,
)
from transcriptx.core.utils.canonicalization import compute_transcript_identity_hash
from transcriptx.core.domain.canonical_transcript import CanonicalTranscript
from transcriptx.core.pipeline.requirements_resolver import ModuleRequirementsResolver
from transcriptx.core.utils.config import get_config
from transcriptx.core.viz.charts import require_plotly

logger = get_logger()


def run_analysis_pipeline(
    target: AnalysisTargetRef | None = None,
    selected_modules: List[str] | None = None,
    skip_speaker_mapping: bool = False,
    speaker_options: "SpeakerRunOptions | None" = None,
    parallel: bool = False,
    max_workers: int = 4,
    config: Optional[Any] = None,  # Optional config parameter for dependency injection
    persist: bool = False,
    rerun_mode: str = "new-run",
    transcript_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the analysis pipeline on a transcript or GroupRef.

    This function orchestrates the execution of multiple analysis modules
    on a transcript file using the DAG pipeline for proper dependency management.

    Args:
        target: AnalysisTargetRef (TranscriptRef or GroupRef)
        selected_modules: List of analysis module names to run
        skip_speaker_mapping: Skip speaker mapping if already done (deprecated, kept for compatibility)
        speaker_options: Run-level speaker options for anonymisation and inclusion

    Returns:
        Dictionary containing analysis results and metadata

    Raises:
        FileNotFoundError: If transcript file doesn't exist
        ValueError: If transcript file is invalid or modules are invalid
        Exception: For other analysis errors
    """
    if target is None and transcript_path is not None:
        target = TranscriptRef(path=transcript_path)
    if target is None:
        raise ValueError("Analysis target must be provided")
    if selected_modules is None:
        raise ValueError("selected_modules must be provided")

    _ensure_tokenizers_parallelism()
    ensure_data_dirs()
    scope, members = resolve_analysis_target(target)
    resolved_paths = [member.file_path for member in members]
    if scope.scope_type == "transcript" and len(resolved_paths) == 1:
        return _run_single_analysis_pipeline(
            transcript_path=resolved_paths[0],
            selected_modules=selected_modules,
            skip_speaker_mapping=skip_speaker_mapping,
            speaker_options=speaker_options,
            parallel=parallel,
            max_workers=max_workers,
            config=config,
            persist=persist,
            rerun_mode=rerun_mode,
        )

    logger.info(
        f"Starting group analysis pipeline for {len(resolved_paths)} transcripts with modules: "
        f"{', '.join(selected_modules)}"
    )

    per_transcript_results: List[PerTranscriptResult] = []
    group_errors: List[str] = []
    for index, transcript_path in enumerate(resolved_paths):
        single_result = _run_single_analysis_pipeline(
            transcript_path=transcript_path,
            selected_modules=selected_modules,
            skip_speaker_mapping=skip_speaker_mapping,
            speaker_options=speaker_options,
            parallel=parallel,
            max_workers=max_workers,
            config=config,
            persist=persist,
            rerun_mode=rerun_mode,
        )
        per_transcript_results.append(
            PerTranscriptResult(
                transcript_path=transcript_path,
                transcript_key=single_result.get("transcript_key", ""),
                run_id=single_result.get("run_id", ""),
                order_index=index,
                output_dir=single_result.get("output_dir", ""),
                module_results=single_result.get("module_results", {}),
            )
        )
        group_errors.extend(single_result.get("errors", []))

    metadata = {}
    group_key: Optional[str] = None
    group_uuid: Optional[str] = None
    if scope.scope_type == "group":
        group_key = scope.key
        group_uuid = scope.uuid
        metadata["group_uuid"] = scope.uuid
        metadata["group_key"] = scope.key
    transcript_set = TranscriptSet.create(
        transcript_ids=resolved_paths,
        name=scope.display_name,
        metadata=metadata,
        key=group_key,
    )

    group_config = config or get_config()
    if not group_config.group_analysis.enabled:
        return {
            "status": "completed",
            "group_key": transcript_set.key,
            "transcript_set": transcript_set.to_dict(),
            "transcripts": [result.to_dict() for result in per_transcript_results],
            "errors": group_errors,
            "warning": "Group analysis is disabled in config; aggregation skipped.",
        }

    # Phase 2: speaker normalization (infrastructure)
    from transcriptx.core.pipeline.speaker_normalizer import (
        normalize_speakers_across_transcripts,
    )

    canonical_speaker_map = normalize_speakers_across_transcripts(
        per_transcript_results
    )

    # Phase 2: group aggregation
    from transcriptx.core.analysis.stats.aggregation import aggregate_stats_group
    from transcriptx.core.analysis.aggregation.sentiment import (
        aggregate_sentiment_group,
    )
    from transcriptx.core.analysis.aggregation.ner import aggregate_ner_group
    from transcriptx.core.analysis.aggregation.entity_sentiment import (
        aggregate_entity_sentiment_group,
    )
    from transcriptx.core.analysis.aggregation.topics import aggregate_topics_group
    from transcriptx.core.analysis.aggregation.emotion import aggregate_emotion_group
    from transcriptx.core.analysis.aggregation.interactions import (
        aggregate_interactions_group,
    )
    from transcriptx.core.output.group_output_service import GroupOutputService
    from transcriptx.core.utils.group_output_utils import (
        get_group_module_dir,
        write_group_module_json,
        write_group_module_csv,
    )

    group_run_id = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    member_uuids = [member.uuid for member in members]
    if group_uuid is None:
        raise ValueError("Group scope is required for group output paths.")
    group_output_service = GroupOutputService(
        group_uuid=group_uuid,
        run_id=group_run_id,
        output_dir=group_config.group_analysis.output_dir,
        scaffold_by_session=group_config.group_analysis.scaffold_by_session,
        scaffold_by_speaker=group_config.group_analysis.scaffold_by_speaker,
        scaffold_comparisons=group_config.group_analysis.scaffold_comparisons,
    )

    stats_group_results = {}
    if group_config.group_analysis.enable_stats_aggregation:
        stats_group_results = aggregate_stats_group(
            per_transcript_results, canonical_speaker_map, transcript_set
        )

    if stats_group_results:
        group_output_service.save_session_table(stats_group_results["session_table"])
        group_output_service.save_combined_json(
            stats_group_results, name="stats_group_summary"
        )
        group_output_service.save_combined_csv(
            stats_group_results["speaker_aggregates"], name="speaker_aggregates"
        )

    sentiment_group_results = aggregate_sentiment_group(
        per_transcript_results, canonical_speaker_map, transcript_set
    )
    if sentiment_group_results:
        group_output_service.save_combined_json(
            sentiment_group_results, name="sentiment_group_summary"
        )
        group_output_service.save_combined_csv(
            sentiment_group_results["session_table"], name="sentiment_session_table"
        )
        group_output_service.save_combined_csv(
            sentiment_group_results["speaker_aggregates"],
            name="sentiment_speaker_aggregates",
        )

    ner_summary = None
    ner_mentions_index = None
    if "ner" in selected_modules:
        ner_results = aggregate_ner_group(
            per_transcript_results, canonical_speaker_map, transcript_set
        )
        if ner_results is not None:
            ner_tables, ner_summary, ner_mentions_index = ner_results
            ner_dir = get_group_module_dir(group_output_service.base_dir, "ner")
            write_group_module_json(ner_dir, "ner_group_summary", ner_summary)
            write_group_module_csv(
                ner_dir, "by_session", "ner_session_entities", ner_tables["by_session"]
            )
            write_group_module_csv(
                ner_dir, "by_speaker", "ner_speaker_entities", ner_tables["by_speaker"]
            )

    entity_sentiment_summary = None
    if "entity_sentiment" in selected_modules:
        if ner_mentions_index:
            entity_sentiment_results = aggregate_entity_sentiment_group(
                per_transcript_results,
                canonical_speaker_map,
                transcript_set,
                ner_mentions_index,
            )
            if entity_sentiment_results is not None:
                entity_sentiment_tables, entity_sentiment_summary = (
                    entity_sentiment_results
                )
                es_dir = get_group_module_dir(
                    group_output_service.base_dir, "entity_sentiment"
                )
                write_group_module_json(
                    es_dir,
                    "entity_sentiment_group_summary",
                    entity_sentiment_summary,
                )
                write_group_module_csv(
                    es_dir,
                    "by_session",
                    "entity_sentiment_session",
                    entity_sentiment_tables["by_session"],
                )
                write_group_module_csv(
                    es_dir,
                    "by_speaker",
                    "entity_sentiment_speaker",
                    entity_sentiment_tables["by_speaker"],
                )
        else:
            logger.warning(
                "[GROUP] entity_sentiment requested but NER mentions are missing; skipping."
            )

    topic_modeling_summary = None
    if "topic_modeling" in selected_modules:
        topic_results = aggregate_topics_group(
            per_transcript_results, canonical_speaker_map, transcript_set
        )
        if topic_results is not None:
            topic_tables, topic_modeling_summary = topic_results
            topics_dir = get_group_module_dir(
                group_output_service.base_dir, "topic_modeling"
            )
            write_group_module_json(
                topics_dir, "topic_modeling_group_summary", topic_modeling_summary
            )
            write_group_module_csv(
                topics_dir,
                "by_session",
                "topic_modeling_session",
                topic_tables["by_session"],
            )
            write_group_module_csv(
                topics_dir,
                "by_speaker",
                "topic_modeling_speaker",
                topic_tables["by_speaker"],
            )

    emotion_group_results = aggregate_emotion_group(
        per_transcript_results, canonical_speaker_map, transcript_set
    )
    if emotion_group_results:
        group_output_service.save_combined_json(
            emotion_group_results, name="emotion_group_summary"
        )
        group_output_service.save_combined_csv(
            emotion_group_results["session_table"], name="emotion_session_table"
        )
        group_output_service.save_combined_csv(
            emotion_group_results["speaker_aggregates"],
            name="emotion_speaker_aggregates",
        )

    interactions_group_results = aggregate_interactions_group(
        per_transcript_results, canonical_speaker_map, transcript_set
    )
    if interactions_group_results:
        group_output_service.save_combined_json(
            interactions_group_results, name="interactions_group_summary"
        )
        group_output_service.save_combined_csv(
            interactions_group_results["session_table"],
            name="interactions_session_table",
        )
        group_output_service.save_combined_csv(
            interactions_group_results["speaker_aggregates"],
            name="interactions_speaker_aggregates",
        )

    wordclouds_summary = None
    if "wordclouds" in selected_modules:
        from transcriptx.core.analysis.aggregation.wordclouds import (
            aggregate_wordclouds_group,
        )
        from transcriptx.core.analysis.wordclouds.analysis import run_group_wordclouds

        grouped, wordclouds_summary = aggregate_wordclouds_group(
            per_transcript_results, canonical_speaker_map
        )
        if wordclouds_summary is not None:
            wordclouds_summary["transcript_set_key"] = transcript_set.key
            wordclouds_summary["transcript_set_name"] = transcript_set.name
        if grouped:
            base_name = group_uuid
            run_group_wordclouds(
                grouped,
                group_output_service.base_dir,
                base_name,
                group_run_id,
            )

    summary_text = (
        f"Group key: {transcript_set.key}\n"
        f"Transcripts: {len(per_transcript_results)}\n"
        f"Run ID: {group_run_id}\n"
    )
    group_output_service.save_summary(summary_text)
    group_output_service.write_group_manifest(
        group_id=group_uuid,
        group_key=group_key or transcript_set.key,
        transcript_file_uuids=member_uuids,
        transcript_paths=resolved_paths,
        run_id=group_run_id,
    )

    group_results: Dict[str, Any] = {
        "status": "completed",
        "group_key": transcript_set.key,
        "group_uuid": group_uuid,
        "group_run_id": group_run_id,
        "group_output_dir": str(group_output_service.base_dir),
        "transcript_set": transcript_set.to_dict(),
        "transcripts": [result.to_dict() for result in per_transcript_results],
        "errors": group_errors,
        "aggregations": {
            "stats": stats_group_results,
            "sentiment": sentiment_group_results,
            "ner": ner_summary,
            "entity_sentiment": entity_sentiment_summary,
            "topic_modeling": topic_modeling_summary,
            "emotion": emotion_group_results,
            "interactions": interactions_group_results,
            "wordclouds": wordclouds_summary,
        },
        "canonical_speaker_map": {
            "transcript_to_speakers": canonical_speaker_map.transcript_to_speakers,
            "canonical_to_display": canonical_speaker_map.canonical_to_display,
        },
    }

    return group_results


def _run_single_analysis_pipeline(
    transcript_path: str,
    selected_modules: List[str],
    skip_speaker_mapping: bool = False,
    speaker_options: "SpeakerRunOptions | None" = None,
    parallel: bool = False,
    max_workers: int = 4,
    config: Optional[Any] = None,  # Optional config parameter for dependency injection
    persist: bool = False,
    rerun_mode: str = "new-run",
) -> Dict[str, Any]:
    """
    Run the analysis pipeline on a single transcript.

    This is the existing single-transcript execution path, extracted to support
    multi-transcript analysis without altering the core logic.
    """
    logger.info(
        f"Starting analysis pipeline for {transcript_path} with modules: {', '.join(selected_modules)}"
    )

    # Validate inputs
    validate_transcript(transcript_path)

    # Validate dynamic chart requirements before any artifact writes
    pipeline_config = config or get_config()
    if getattr(pipeline_config.output, "dynamic_charts", "auto") == "on":
        require_plotly()

    # Get transcript metrics for estimation
    transcript_segments_count = None
    transcript_word_count = None
    segments = []
    try:
        from transcriptx.io.transcript_loader import load_canonical_transcript

        canonical = load_canonical_transcript(transcript_path)
        segments = canonical.segments
        transcript_segments_count = len(segments)
        transcript_word_count = sum(
            len(seg.get("text", "").split()) for seg in segments
        )
    except Exception:
        pass

    # Show pipeline time estimate
    try:
        estimator = PerformanceEstimator()
        estimate = estimator.estimate_pipeline_time(
            modules=selected_modules,
            transcript_segments=transcript_segments_count,
            transcript_words=transcript_word_count,
        )
        if estimate.get("estimated_seconds") is not None:
            estimate_str = format_time_estimate(estimate)
            logger.info(f"Estimated pipeline time: {estimate_str}")
    except Exception:
        pass  # Don't fail if estimation fails

    # Compute canonical transcript and run directory
    canonical = CanonicalTranscript.from_segments(segments)
    transcript_content_hash_full = canonical.content_hash
    transcript_identity_hash = compute_transcript_identity_hash(segments)
    transcript_key = transcript_identity_hash
    transcript_file_hash = compute_file_hash(Path(transcript_path))
    run_id = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    # Register transcript and get slug for human-friendly folder name
    from transcriptx.core.utils.slug_manager import register_transcript
    from transcriptx.core.utils._path_core import get_canonical_base_name

    source_basename = get_canonical_base_name(transcript_path)
    slug = register_transcript(
        transcript_key=transcript_key,
        transcript_path=transcript_path,
        run_id=run_id,
        source_basename=source_basename,
        source_path=transcript_path,
    )

    # Use slug-based folder structure: outputs/<slug>/<run_id>/
    output_dir = str(Path(OUTPUTS_DIR) / slug / run_id)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    set_transcript_output_dir(transcript_path, output_dir)

    # Resolve effective config and apply draft override (if any)
    from transcriptx.core.config.persistence import (
        load_draft_override,
        load_project_config,
        save_run_override,
        save_run_effective,
        compute_config_hash,
        clear_draft_override,
        CONFIG_SCHEMA_VERSION,
    )
    from transcriptx.core.config.resolver import resolve_effective_config
    from transcriptx.core.config.validation import validate_config
    from transcriptx.core.utils.config import set_config
    from transcriptx.core.viz.charts import require_plotly

    run_dir = Path(output_dir)
    draft_override = load_draft_override()
    applied_draft = False
    if draft_override:
        save_run_override(run_dir, draft_override)
        applied_draft = True

    resolved = resolve_effective_config(run_dir=run_dir)
    validation_errors = validate_config(resolved.effective_dict_nested)
    if validation_errors:
        error_lines = []
        for key, errors in validation_errors.items():
            for err in errors:
                error_lines.append(f"{key}: {err.message}")
        raise ValueError(
            "Configuration validation failed before run:\n" + "\n".join(error_lines)
        )

    save_run_effective(run_dir, resolved.effective_dict_nested)
    config_hash = compute_config_hash(resolved.effective_dict_nested)

    config_source = "default"
    if draft_override:
        config_source = "run_override"
    else:
        project_config = load_project_config()
        if project_config:
            config_source = "project"

    # Use resolved config for downstream pipeline usage
    config = resolved.effective_config
    set_config(config)

    if getattr(config.output, "dynamic_charts", "auto") == "on":
        require_plotly()

    run_report = RunReport(transcript_hash=transcript_key, run_id=run_id)
    requirements_resolver = ModuleRequirementsResolver(
        capabilities=canonical.capabilities,
        has_db=persist,
    )

    # Initialize database canonical integration only if --persist is set
    db_coordinator = None
    if persist:
        try:
            from transcriptx.database.pipeline_run_service import PipelineRunCoordinator

            analysis_config = getattr(config, "analysis", None)
            if isinstance(analysis_config, dict):
                analysis_mode = analysis_config.get("analysis_mode", "quick")
                quality_profile = analysis_config.get(
                    "quality_filtering_profile", "balanced"
                )
            else:
                analysis_mode = getattr(analysis_config, "analysis_mode", "quick")
                quality_profile = getattr(
                    analysis_config, "quality_filtering_profile", "balanced"
                )

            pipeline_config = {
                "modules": selected_modules,
                "analysis_mode": analysis_mode,
                "quality_profile": quality_profile,
            }
            db_coordinator = PipelineRunCoordinator(
                transcript_path=transcript_path,
                selected_modules=selected_modules,
                pipeline_config=pipeline_config,
                cli_args={"rerun_mode": rerun_mode},
                rerun_mode=rerun_mode,
            )
            db_coordinator.start()
            logger.info("✅ Database canonical integration initialized")
        except Exception as e:
            logger.warning(f"⚠️ Database canonical integration failed: {e}")

    # Create and configure DAG pipeline
    dag_pipeline = create_dag_pipeline()

    # Wrap pipeline execution with performance logging
    file_name = Path(transcript_path).name
    def _safe_db_id(value: Any) -> Optional[int]:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    pipeline_run_id = _safe_db_id(
        db_coordinator.pipeline_run.id
        if db_coordinator and getattr(db_coordinator, "pipeline_run", None)
        else None
    )
    transcript_file_id = _safe_db_id(
        db_coordinator.transcript_file.id
        if db_coordinator and getattr(db_coordinator, "transcript_file", None)
        else None
    )
    with TimedJob(
        "pipeline.run",
        file_name,
        pipeline_run_id=pipeline_run_id,
        transcript_file_id=transcript_file_id,
    ) as job:
        job.add_metadata(
            {
                "transcript_path": transcript_path,
                "modules": selected_modules,
                "parallel": parallel,
            }
        )
        if transcript_segments_count is not None:
            job.add_metadata({"transcript_segments_count": transcript_segments_count})
        if transcript_word_count is not None:
            job.add_metadata({"transcript_word_count": transcript_word_count})

        # Execute pipeline using DAG
        start_time = time.time()
        try:
            results = dag_pipeline.execute_pipeline(
                transcript_path=transcript_path,
                selected_modules=selected_modules,
                skip_speaker_mapping=skip_speaker_mapping,
                speaker_options=speaker_options,
                parallel=parallel,
                max_workers=max_workers,
                db_coordinator=db_coordinator,
                output_dir=output_dir,
                transcript_key=transcript_key,
                run_id=run_id,
                run_report=run_report,
                requirements_resolver=requirements_resolver,
            )
            logger.info("✅ DAG pipeline execution completed successfully")
        except Exception as e:
            if db_coordinator:
                db_coordinator.finish(success=False)
            logger.error(f"❌ DAG pipeline failed: {e}")
            raise

        # Generate and display output summary
        summary = generate_comprehensive_output_summary(
            transcript_path=transcript_path,
            selected_modules=selected_modules,
            modules_run=results.get("modules_run", []),
            errors=results.get("errors", []),
        )

        # Build lightweight output manifest for the run
        write_output_manifest(
            run_dir=Path(output_dir),
            run_id=run_id,
            transcript_key=transcript_key,
            modules_enabled=selected_modules,
        )

        # Display results to user
        display_output_summary_to_user(summary)

        # Log pipeline completion
        end_time = time.time()
        duration = end_time - start_time
        log_pipeline_complete(
            transcript_path, results.get("modules_run", []), results.get("errors", [])
        )

        # Add modules run count to metadata
        job.add_metadata(
            {
                "modules_run_count": len(results.get("modules_run", [])),
                "errors_count": len(results.get("errors", [])),
            }
        )

        if db_coordinator:
            db_coordinator.finish(success=len(results.get("errors", [])) == 0)

    # Prepare results dictionary
    pipeline_results = {
        "transcript_path": transcript_path,
        "selected_modules": selected_modules,
        "modules_run": results.get("modules_run", []),
        "errors": results.get("errors", []),
        "duration": duration,
        "summary": summary,
        "execution_order": results.get("execution_order", []),
        "cache_hits": results.get("cache_hits", []),
        "output_dir": output_dir,
        "transcript_key": transcript_key,
        "run_id": run_id,
        "module_results": results.get("module_results", {}),
    }

    run_report.errors.extend(results.get("errors", []))

    # Update processing state with analysis results
    try:
        from transcriptx.core.utils.state_schema import update_analysis_state
        from transcriptx.cli.processing_state import (
            load_processing_state,
            save_processing_state,
        )
        from transcriptx.core.utils.paths import DATA_DIR

        processing_state_file = Path(DATA_DIR) / "processing_state.json"
        if processing_state_file.exists():
            state = load_processing_state()
            processed_files = state.get("processed_files", {})

            # Find entry matching this transcript
            entry_found = False
            for file_key, entry in processed_files.items():
                if entry.get("transcript_path") == transcript_path:
                    # Update entry with analysis results
                    updated_entry = update_analysis_state(entry, pipeline_results)
                    processed_files[file_key] = updated_entry
                    entry_found = True
                    logger.debug(
                        f"Updated processing state with analysis results for {transcript_path}"
                    )
                    break

            if entry_found:
                state["processed_files"] = processed_files
                save_processing_state(state)
            else:
                logger.warning(
                    f"Transcript {transcript_path} not found in processing state, skipping state update"
                )
        else:
            logger.debug("Processing state file does not exist, skipping state update")
    except Exception as e:
        # Don't fail analysis if state update fails
        logger.warning(f"Failed to update processing state with analysis results: {e}")

    # Save run report
    try:
        report_path = save_run_report(run_report, output_dir)
        logger.info(f"Created run report: {report_path}")
    except Exception as e:
        logger.warning(f"Failed to create run report: {e}")

    # Create and save run manifest for reproducibility
    manifest_written = False
    try:
        artifact_index: List[Dict[str, Any]] = []
        output_root = Path(output_dir)
        if output_root.exists():
            for file_path in sorted(output_root.rglob("*")):
                if not file_path.is_file():
                    continue
                if file_path.name == "manifest.json":
                    continue
                relative_path = file_path.relative_to(output_root).as_posix()
                artifact_index.append(
                    {
                        "path": relative_path,
                        "checksum": compute_file_hash(file_path),
                    }
                )
        manifest = create_run_manifest(
            transcript_hash=transcript_file_hash or transcript_key,
            transcript_file_hash=transcript_file_hash,
            transcript_identity_hash=transcript_identity_hash,
            transcript_content_hash_full=transcript_content_hash_full,
            canonical_schema_version=canonical.schema_version,
            selected_modules=selected_modules,
            artifact_index=artifact_index,
            config_hash=config_hash,
            config_effective_path=".transcriptx/run_config_effective.json",
            config_override_path=(
                ".transcriptx/run_config_override.json" if draft_override else None
            ),
            config_schema_version=CONFIG_SCHEMA_VERSION,
            config_source=config_source,
            transcript_path=transcript_path,
            source_basename=source_basename,
            source_path=transcript_path,
            run_id=run_id,
        )
        manifest_path = save_run_manifest(manifest, output_dir)
        logger.info(f"Created run manifest: {manifest_path}")
        manifest_written = True
    except Exception as e:
        logger.warning(f"Failed to create run manifest: {e}")

    if manifest_written and applied_draft:
        clear_draft_override()

    if db_coordinator:
        db_coordinator.close()
    clear_transcript_output_dir(transcript_path)

    return pipeline_results


def run_analysis_pipeline_from_file(
    transcript_path: str,
    modules: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to run analysis pipeline from file path.

    Args:
        transcript_path: Path to the transcript JSON file
        modules: List of analysis modules to run (default: all)

    Returns:
        Dictionary containing results and metadata
    """
    if modules is None:
        modules = get_default_modules(transcript_path)

    return run_analysis_pipeline(
        target=TranscriptRef(path=transcript_path),
        selected_modules=modules,
    )


def get_available_modules() -> List[str]:
    """Get list of available analysis modules."""
    return list(get_available_modules_from_registry())


def get_default_modules(
    transcript_targets: Optional[List[object]] = None,
    *,
    audio_resolver: Optional[Callable[[object], bool]] = None,
    dep_resolver: Optional[Callable[[object], bool]] = None,
    include_heavy: bool = True,
    include_excluded_from_default: bool = False,
) -> List[str]:
    """Get list of modules used for default analysis runs."""
    return list(
        get_default_modules_from_registry(
            transcript_targets,
            audio_resolver=audio_resolver,
            dep_resolver=dep_resolver,
            include_heavy=include_heavy,
            include_excluded_from_default=include_excluded_from_default,
        )
    )
