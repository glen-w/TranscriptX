"""
Unified analysis pipeline orchestrator for TranscriptX.

This module provides a thin orchestration layer that coordinates
the DAG pipeline with preprocessing and output reporting.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from transcriptx.core.utils.native_threads import ensure_native_thread_env_defaults

# Suppress tokenizer warnings about parallelism to prevent console spam.
# Also pin BLAS/OpenMP to 1 when unset — oversubscription (esp. BERTopic/
# UMAP/HDBSCAN) has been observed to hang native fits indefinitely.
_ensure_tokenizers_parallelism = ensure_native_thread_env_defaults

# Pin before any analysis/extra import can load Numba/UMAP (pool size is sticky).
_ensure_tokenizers_parallelism()

from transcriptx.core.utils.logger import get_logger, log_pipeline_complete
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
from transcriptx.core.pipeline.run_orchestrator import RunOrchestrator
from transcriptx.core.pipeline.run_control import (
    TERMINATION_CANCELLATION,
    pipeline_is_cancelled,
)
from transcriptx.core.pipeline.contracts import RunRequest, TranscriptSource
from transcriptx.core.pipeline.pipeline_legacy_compat import (
    apply_legacy_resolver_compat,
    enforce_managed_transcript_gate,
)
from transcriptx.core.pipeline.module_registry import (
    get_available_modules as get_available_modules_from_registry,
    get_default_modules as get_default_modules_from_registry,
)
from transcriptx.core.utils.paths import OUTPUTS_DIR, ensure_data_dirs
from transcriptx.core.utils.config import get_config
from transcriptx.core.viz.charts import require_plotly

logger = get_logger()
_orchestrator = RunOrchestrator()


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
            include_unidentified=manifest.include_unidentified_speakers,
            allow_unnamed_speakers=manifest.allow_unnamed_speakers,
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

    from transcriptx.core.observability.run_performance.recorder import (
        PENDING_RUN_ID,
        RecorderState,
        RunPerformanceRecorder,
    )
    from transcriptx.core.utils.analysis_locks import group_analysis_lock

    group_recorder = RunPerformanceRecorder(run_id=PENDING_RUN_ID, target_type="group")
    group_recorder.start_wall_clock()
    # Do not bind: member RunOrchestrator instances own the active ContextVar.

    group_uuid = scope.uuid
    if not group_uuid:
        raise ValueError("Group scope is required for group analysis lock.")

    per_transcript_results: List[PerTranscriptResult] = []
    group_errors: List[str] = []
    cancelled = False
    with group_analysis_lock(str(group_uuid)):
        try:
            for index, transcript_path in enumerate(resolved_paths):
                if pipeline_is_cancelled():
                    cancelled = True
                    group_errors.append("Analysis cancelled")
                    break
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
                if single_result.get("termination_reason") == TERMINATION_CANCELLATION:
                    cancelled = True
                    group_errors.append("Analysis cancelled")
                    break

            result = finalize_group_analysis(
                scope=scope,
                members=members,
                resolved_paths=resolved_paths,
                per_transcript_results=per_transcript_results,
                group_errors=group_errors,
                selected_modules=selected_modules,
                config=config,
                performance_recorder=group_recorder,
            )
            if cancelled:
                result["termination_reason"] = TERMINATION_CANCELLATION
                result["status"] = "aborted"
            return result
        finally:
            # Emergency cleanup only: if finalize never stopped the wall, stop without write.
            if group_recorder.state == RecorderState.running:
                try:
                    group_recorder.stop_wall_clock()
                except Exception:
                    logger.exception("group run performance emergency wall stop failed")


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

    allow_unmanaged = os.getenv("TRANSCRIPTX_ALLOW_UNMANAGED_TRANSCRIPTS", "0") == "1"
    enforce_managed_transcript_gate(
        transcript_path,
        allow_unmanaged=allow_unmanaged,
    )

    request = RunRequest(
        transcript_source=TranscriptSource(kind="local_file", value=transcript_path),
        selected_modules=list(selected_modules),
        run_id_override=run_id_override,
        output_dir_override=output_dir_override,
        parallel=parallel,
        max_workers=max_workers,
        rerun_mode=rerun_mode,
        persist=persist,
    )
    apply_legacy_resolver_compat(run_dir=Path(OUTPUTS_DIR), request=request)

    pipeline_config = config or get_config()
    validate_transcript(transcript_path)
    if getattr(pipeline_config.output, "dynamic_charts", "auto") == "on":
        require_plotly()
    if parallel or max_workers != 4:
        logger.warning(
            "parallel/max_workers are deprecated at API edge only; core execution is sequential"
        )
    result = _orchestrator.run(
        transcript_path=transcript_path,
        request=request,
        speaker_options=speaker_options,
        on_event=on_event,
    )
    log_pipeline_complete(transcript_path, result.modules_run, result.errors)
    skipped_modules = getattr(result, "skipped_modules", [])
    return {
        "transcript_path": result.transcript_path,
        "selected_modules": result.selected_modules,
        "modules_run": result.modules_run,
        "skipped_modules": skipped_modules,
        "errors": result.errors,
        "duration": result.duration,
        "summary": result.summary,
        "execution_order": result.execution_order,
        "cache_hits": result.cache_hits,
        "output_dir": result.output_dir,
        "transcript_key": result.transcript_key,
        "run_id": result.run_id,
        "module_results": result.module_results,
        "status": result.status,
        "execution_status": result.execution_status,
        "final_status": result.final_status,
        "persistence_outcomes": [
            {
                "name": o.name,
                "success": o.success,
                "severity": o.severity,
                "error_kind": o.error_kind.value if o.error_kind else None,
                "error_message": o.error_message,
            }
            for o in result.persistence_outcomes
        ],
        "termination_reason": result.termination_reason,
        "schema_version": result.schema_version,
    }


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
    include_legacy: Optional[bool] = None,
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
            include_legacy=include_legacy,
        )
    )
