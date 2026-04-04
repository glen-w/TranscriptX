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
from transcriptx.core.pipeline.dag_pipeline import create_dag_pipeline
from transcriptx.core.pipeline.group_analysis_runner import finalize_group_analysis
from transcriptx.core.pipeline.preprocessing import validate_transcript
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.run_schema import RunManifestInput
from transcriptx.core.pipeline.run_options import SpeakerRunOptions
from transcriptx.core.pipeline.target_resolver import (
    AnalysisTargetRef,
    TranscriptRef,
    resolve_analysis_target,
)
from transcriptx.core.pipeline.output_reporter import (
    generate_comprehensive_output_summary,
    display_output_summary_to_user,
    print_review_before_run,
    print_compact_post_run_summary,
)
from transcriptx.core.pipeline.pipeline_write_phases import (
    persist_canonical_results_and_artifacts,
)
from transcriptx.core.pipeline.module_registry import (
    get_available_modules as get_available_modules_from_registry,
    get_default_modules as get_default_modules_from_registry,
)
from transcriptx.core.utils.paths import OUTPUTS_DIR, ensure_data_dirs
from transcriptx.core.utils._path_core import (
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
    manifest: Optional[RunManifestInput] = None,
    *,
    target: AnalysisTargetRef | None = None,
    selected_modules: List[str] | None = None,
    speaker_options: "SpeakerRunOptions | None" = None,
    parallel: bool = False,
    max_workers: int = 4,
    config: Optional[Any] = None,  # Optional config parameter for dependency injection
    persist: bool = False,
    rerun_mode: str = "new-run",
    transcript_path: Optional[str] = None,
    on_event: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run the analysis pipeline on a transcript or GroupRef.

    on_event: optional callable(event_dict) forwarded to the single-transcript
    DAG execution path. Best-effort — the pipeline continues even if it raises.
    Only used for single-transcript runs; group runs do not forward it.
    """
    # Normalize from manifest when provided (canonical path)
    if manifest is not None:
        target = TranscriptRef(path=manifest.transcript_path)
        if manifest.modules == ["all"]:
            selected_modules = get_default_modules_from_registry(
                [manifest.transcript_path]
            )
        else:
            selected_modules = list(manifest.modules)
        speaker_options = SpeakerRunOptions(
            include_unidentified=manifest.include_unidentified_speakers
        )
        persist = manifest.persist
        transcript_path = manifest.transcript_path
    else:
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
        run_id_override = manifest.run_id if manifest else None
        output_dir_override = manifest.output_dir if manifest else None
        return _run_single_analysis_pipeline(
            transcript_path=resolved_paths[0],
            selected_modules=selected_modules,
            speaker_options=speaker_options,
            parallel=parallel,
            max_workers=max_workers,
            config=config,
            persist=persist,
            rerun_mode=rerun_mode,
            run_id_override=run_id_override,
            output_dir_override=output_dir_override,
            on_event=on_event,
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
            speaker_options=speaker_options,
            parallel=parallel,
            max_workers=max_workers,
            config=config,
            persist=persist,
            rerun_mode=rerun_mode,
            run_id_override=None,
            output_dir_override=None,
        )
        per_transcript_results.append(
            PerTranscriptResult(
                transcript_path=transcript_path,
                transcript_key=single_result.get("transcript_key", ""),
                run_id=single_result.get("run_id", ""),
                order_index=index,
                output_dir=single_result.get("output_dir", ""),
                module_results=single_result.get("module_results", {}),
                modules_run=list(single_result.get("modules_run", [])),
                skipped_modules=list(single_result.get("skipped_modules", [])),
            )
        )
        group_errors.extend(single_result.get("errors", []))

    return finalize_group_analysis(
        scope=scope,
        members=members,
        resolved_paths=resolved_paths,
        per_transcript_results=per_transcript_results,
        group_errors=group_errors,
        selected_modules=selected_modules,
        config=config,
    )


def _run_single_analysis_pipeline(
    transcript_path: str,
    selected_modules: List[str],
    speaker_options: "SpeakerRunOptions | None" = None,
    parallel: bool = False,
    max_workers: int = 4,
    config: Optional[Any] = None,  # Optional config parameter for dependency injection
    persist: bool = False,
    rerun_mode: str = "new-run",
    run_id_override: Optional[str] = None,
    output_dir_override: Optional[str] = None,
    on_event: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Run the analysis pipeline on a single transcript.

    on_event: optional callable(event_dict) forwarded to the DAG pipeline.
    Best-effort — the pipeline continues even if the hook raises.
    """
    logger.info(
        f"Starting analysis pipeline for {transcript_path} with modules: {', '.join(selected_modules)}"
    )

    pipeline_config = config or get_config()

    # Validate inputs
    validate_transcript(transcript_path)

    # Validate dynamic chart requirements before any artifact writes
    if getattr(pipeline_config.output, "dynamic_charts", "auto") == "on":
        require_plotly()

    # Get transcript metrics for estimation
    segments = []
    try:
        from transcriptx.io.transcript_loader import load_canonical_transcript

        canonical = load_canonical_transcript(transcript_path)
        segments = canonical.segments
    except Exception as e:
        logger.exception("Failed to load transcript for pipeline; cannot continue")
        raise RuntimeError(f"Failed to load transcript {transcript_path}: {e}") from e

    # Compute canonical transcript and run directory
    canonical = CanonicalTranscript.from_segments(segments)
    transcript_content_hash_full = canonical.content_hash
    transcript_identity_hash = compute_transcript_identity_hash(segments)
    transcript_key = transcript_identity_hash
    transcript_file_hash = compute_file_hash(Path(transcript_path))
    run_id = (
        run_id_override
        if run_id_override
        else f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    )

    # Register transcript and get slug for human-friendly folder name
    from transcriptx.core.utils.slug_manager import register_transcript
    from transcriptx.core.utils._path_core import get_canonical_base_name
    from transcriptx.io.import_metadata_sidecar import validate_managed_transcript

    source_basename = get_canonical_base_name(transcript_path)
    managed_validation = validate_managed_transcript(transcript_path)
    allow_unmanaged = os.getenv("TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS", "0") == "1"
    if not managed_validation.ok and not allow_unmanaged:
        raise ValueError(
            "Cannot register non-managed transcript: "
            f"{managed_validation.category.value} ({managed_validation.message})"
        )
    if not managed_validation.ok and allow_unmanaged:
        logger.warning(
            "Proceeding with unmanaged transcript because "
            "TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS=1: %s (%s)",
            managed_validation.category.value,
            managed_validation.message,
        )
    slug = register_transcript(
        transcript_key=transcript_key,
        transcript_path=transcript_path,
        run_id=run_id,
        source_basename=source_basename,
        source_path=transcript_path,
    )

    # Use slug-based folder structure: outputs/<slug>/<run_id>/ (or output_dir_override/slug/run_id)
    base_output = output_dir_override if output_dir_override else OUTPUTS_DIR
    output_dir = str(Path(base_output) / slug / run_id)
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
        has_db=False,
    )

    # Create and configure DAG pipeline
    dag_pipeline = create_dag_pipeline()

    # Review before run: compute and print (engine returns data, pipeline prints)
    try:
        review = dag_pipeline.compute_review_before_run(
            transcript_path=transcript_path,
            selected_modules=selected_modules,
            output_dir=output_dir,
            requirements_resolver=requirements_resolver,
            speaker_options=speaker_options,
            transcript_key=transcript_key,
            run_id=run_id,
        )
        print_review_before_run(review)
    except Exception as e:
        logger.warning(f"Could not compute review before run: {e}")

    # Execute pipeline using DAG
    start_time = time.time()
    try:
        results = dag_pipeline.execute_pipeline(
            transcript_path=transcript_path,
            selected_modules=selected_modules,
            speaker_options=speaker_options,
            parallel=parallel,
            max_workers=max_workers,
            output_dir=output_dir,
            transcript_key=transcript_key,
            run_id=run_id,
            run_report=run_report,
            requirements_resolver=requirements_resolver,
            on_event=on_event,
        )
        logger.info("✅ DAG pipeline execution completed successfully")
    except Exception as e:
        logger.error(f"❌ DAG pipeline failed: {e}")
        raise

    # Generate and display output summary
    summary = generate_comprehensive_output_summary(
        transcript_path=transcript_path,
        selected_modules=selected_modules,
        modules_run=results.get("modules_run", []),
        errors=results.get("errors", []),
        skipped_modules=results.get("skipped_modules", []),
    )

    # Canonical write-side persistence seam:
    # 1) normalize + persist run outcomes
    # 2) persist artifact manifest
    persist_canonical_results_and_artifacts(
        run_dir=Path(output_dir),
        run_id=run_id,
        transcript_key=transcript_key,
        modules_enabled=selected_modules,
        results=results,
    )

    # Display results to user
    display_output_summary_to_user(summary)
    print_compact_post_run_summary(output_dir, results)

    # Log pipeline completion
    end_time = time.time()
    duration = end_time - start_time
    log_pipeline_complete(
        transcript_path, results.get("modules_run", []), results.get("errors", [])
    )

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
        from transcriptx.core.utils.processing_state import (
            find_processed_entry_for_path,
            load_processing_state,
            save_processing_state,
        )
        from transcriptx.core.utils.paths import PROCESSING_STATE_FILE

        if PROCESSING_STATE_FILE.exists():
            state = load_processing_state()
            processed_files = state.get("processed_files", {})

            # Match by resolved paths (state may store resolved paths; caller may not)
            file_key, entry = find_processed_entry_for_path(
                transcript_path, state=state
            )
            if file_key is not None and entry is not None:
                updated_entry = update_analysis_state(entry, pipeline_results)
                processed_files[file_key] = updated_entry
                logger.debug(
                    f"Updated processing state with analysis results for {transcript_path}"
                )

            if file_key is not None:
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


def get_available_modules(core_mode: Optional[bool] = None) -> List[str]:
    """Get list of available analysis modules. core_mode from config if None."""
    return list(get_available_modules_from_registry(core_mode=core_mode))


def get_default_modules(
    transcript_targets: Optional[List[object]] = None,
    *,
    audio_resolver: Optional[Callable[[object], bool]] = None,
    dep_resolver: Optional[Callable[[object], bool]] = None,
    include_heavy: bool = True,
    include_excluded_from_default: bool = False,
    for_group: bool = False,
    core_mode: Optional[bool] = None,
) -> List[str]:
    """Get list of modules used for default analysis runs. core_mode from config if None."""
    return list(
        get_default_modules_from_registry(
            transcript_targets,
            audio_resolver=audio_resolver,
            dep_resolver=dep_resolver,
            include_heavy=include_heavy,
            include_excluded_from_default=include_excluded_from_default,
            for_group=for_group,
            core_mode=core_mode,
        )
    )
