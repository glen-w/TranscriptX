"""
Prompt-free analysis workflow. No questionary, rich, click, or typer.

Accepts explicit AnalysisRequest, returns structured AnalysisResult.
Uses ProgressCallback for status updates. Caller is responsible for
output capture if wrapping legacy code that still prints.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, List, MutableMapping, Optional

from transcriptx.app.models.requests import AnalysisRequest, GroupAnalysisRequest
from transcriptx.app.models.results import AnalysisResult
from transcriptx.app.progress import (
    NullProgress,
    ProgressCallback,
    ProgressEvent,
    SnapshotLogHandler,
    update_snapshot_from_event,
)
from transcriptx.core.analysis.selection import (
    apply_analysis_mode_settings,
    filter_modules_by_mode,
)
from transcriptx.core.pipeline.module_registry import (
    get_available_modules,
    get_default_modules,
    get_module_info,
)
from transcriptx.core.utils.audio_availability import has_resolvable_audio
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.run_outcome_truth import project_group_outcomes
from transcriptx.core.pipeline.run_options import SpeakerRunOptions
from transcriptx.core.pipeline.run_schema import RunManifestInput
from transcriptx.core.pipeline.target_resolver import GroupRef, resolve_analysis_target
from transcriptx.core.utils.config import get_config


def _coerce_llm_model_selection(value: Any) -> Any:
    """Normalize request payload to ``LlmModelSelection`` or ``None``.

    ``None`` preserves global-only behaviour. Explicit but invalid payloads
    raise ``ValueError`` (do not silently restore omit semantics).
    """
    if value is None:
        return None
    from transcriptx.core.analysis.llm_support.model_selection import (
        LlmModelSelection,
        validate_llm_model_selection,
    )

    if isinstance(value, LlmModelSelection):
        return validate_llm_model_selection(value)
    if isinstance(value, dict):
        return validate_llm_model_selection(value)
    raise ValueError(
        "llm_model_selection must be a mapping or LlmModelSelection, "
        f"got {type(value).__name__}"
    )


def _append_llm_model_selection_errors(request: Any, errors: list[str]) -> None:
    """Validate explicit request.llm_model_selection into ``errors`` in-place."""
    selection = getattr(request, "llm_model_selection", None)
    if selection is None:
        return
    try:
        _coerce_llm_model_selection(selection)
    except ValueError as exc:
        errors.append(f"Invalid llm_model_selection: {exc}")


@dataclass(frozen=True)
class ValidationOutcome:
    valid: bool
    result: AnalysisResult | None


def _failure_result(
    errors: list[str], *, warnings: list[str] | None = None
) -> AnalysisResult:
    return AnalysisResult(
        success=False,
        run_dir=Path(),
        manifest_path=Path(),
        modules_executed=[],
        warnings=warnings or [],
        errors=errors,
        status="failed",
    )


def _update_snapshot(
    snapshot: Optional[MutableMapping[str, Any]], **fields: Any
) -> None:
    if snapshot is not None:
        snapshot.update(**fields)


def _validate_or_fail(
    snapshot: Optional[MutableMapping[str, Any]],
    request: Any,
    validator: Callable[[Any], list[str]],
) -> ValidationOutcome:
    errors = validator(request)
    if not errors:
        return ValidationOutcome(valid=True, result=None)
    _update_snapshot(
        snapshot,
        status="failed",
        phase="failed",
        error="; ".join(errors),
        latest_event="Validation failed",
    )
    return ValidationOutcome(valid=False, result=_failure_result(errors))


def _modules_unsupported_for_group(module_ids: list[str]) -> list[str]:
    unsupported: list[str] = []
    for module_id in module_ids:
        info = get_module_info(module_id)
        if info is not None and not info.supports_group:
            unsupported.append(module_id)
    return unsupported


def _resolve_modules(
    request_modules: list[str] | None,
    defaults_for_paths: list[str],
    *,
    for_group: bool = False,
) -> tuple[list[str], str | None]:
    available = get_available_modules()
    default = get_default_modules(
        defaults_for_paths,
        audio_resolver=has_resolvable_audio,
        for_group=for_group,
    )
    if request_modules is None or (
        isinstance(request_modules, list) and len(request_modules) == 0
    ):
        return default, None
    if (
        isinstance(request_modules, list)
        and len(request_modules) == 1
        and request_modules[0].lower() == "all"
    ):
        return default, None
    invalid = [module for module in request_modules if module not in available]
    if invalid:
        return [], f"Invalid modules: {', '.join(invalid)}"
    selected = list(request_modules)
    if for_group:
        unsupported = _modules_unsupported_for_group(selected)
        if unsupported:
            return (
                [],
                "Modules not supported for group analysis: " + ", ".join(unsupported),
            )
    return selected, None


def validate_analysis_readiness(request: AnalysisRequest) -> list[str]:
    """
    Pre-run validation. Returns list of error messages; empty if ready.
    """
    errors: list[str] = []
    path = Path(request.transcript_path)
    if not path.exists():
        errors.append(f"Transcript file not found: {path}")
        return errors
    if path.suffix.lower() != ".json":
        errors.append(f"Expected JSON transcript, got: {path.suffix}")
    if request.mode not in ("quick", "full"):
        errors.append(f"Invalid mode: {request.mode}. Must be 'quick' or 'full'")
    valid_profiles = (
        "balanced",
        "academic",
        "business",
        "casual",
        "technical",
        "interview",
    )
    if request.profile and request.profile not in valid_profiles:
        errors.append(f"Invalid profile: {request.profile}")
    if request.modules is not None:
        available = get_available_modules()
        invalid = [m for m in request.modules if m not in available]
        if invalid:
            errors.append(f"Invalid modules: {', '.join(invalid)}")
    _append_llm_model_selection_errors(request, errors)
    return errors


def run_analysis(
    request: AnalysisRequest,
    progress: ProgressCallback | None = None,
    snapshot: Optional[MutableMapping[str, Any]] = None,
) -> AnalysisResult:
    """
    Run single-transcript analysis. No prompts, no prints.

    snapshot: optional mutable dict (e.g. st.session_state["run_progress"]) that
    will be updated in-place via update_snapshot_from_event as the pipeline
    emits structured events.  The caller is responsible for storing it in
    session state before calling this function so that Streamlit reruns can
    read the latest value.
    """
    if progress is None:
        progress = NullProgress()

    path = Path(request.transcript_path)
    if not path.exists():
        _update_snapshot(
            snapshot,
            status="failed",
            phase="failed",
            error=f"Transcript file not found: {path}",
        )
        return _failure_result([f"Transcript file not found: {path}"])

    # -----------------------------------------------------------------------
    # Validation phase
    # -----------------------------------------------------------------------
    _update_snapshot(
        snapshot,
        status="running",
        phase="validating",
        latest_event="Checking inputs…",
    )
    progress.on_stage_start("validating")

    validation = _validate_or_fail(snapshot, request, validate_analysis_readiness)
    if not validation.valid:
        progress.on_stage_complete("validating")
        assert validation.result is not None
        return validation.result
    progress.on_stage_complete("validating")

    selected, module_error = _resolve_modules(request.modules, [str(path)])
    if module_error:
        _update_snapshot(
            snapshot,
            status="failed",
            phase="failed",
            error=module_error,
            latest_event=module_error,
        )
        return _failure_result([module_error])

    apply_analysis_mode_settings(request.mode, request.profile)
    filtered = filter_modules_by_mode(selected, request.mode)

    output_dir_str: str | None = None
    output_config: Any | None = None
    previous_base_output_dir: Any | None = None
    if request.output_dir:
        output_dir_str = str(Path(request.output_dir))
        output_config = get_config()
        previous_base_output_dir = output_config.output.base_output_dir
        output_config.output.base_output_dir = output_dir_str

    # -----------------------------------------------------------------------
    # Pipeline phase — build on_event hook that keeps snapshot up to date
    # -----------------------------------------------------------------------
    if snapshot is not None:
        snap = snapshot
        # Seed snapshot before the run so the UI has something to show immediately
        snap.update(
            status="running",
            phase="running_pipeline",
            total=len(filtered),
            completed=0,
            skipped=0,
            failed=0,
            pct=0.0,
            latest_event=f"Running {len(filtered)} modules…",
            error=None,
        )
        if "recent_logs" not in snap:
            snap["recent_logs"] = []

        def _on_event(event: ProgressEvent) -> None:
            update_snapshot_from_event(snap, event)  # type: ignore[arg-type]
            # Also forward structured event to progress callback
            if hasattr(progress, "on_event"):
                try:
                    progress.on_event(event)  # type: ignore[arg-type]
                except Exception:
                    pass

        on_event: Optional[Callable[..., None]] = _on_event
    else:
        # No snapshot; still forward to progress callback if it supports on_event
        if hasattr(progress, "on_event"):

            def _on_event_only(event: ProgressEvent) -> None:
                try:
                    progress.on_event(event)  # type: ignore[arg-type]
                except Exception:
                    pass

            on_event = _on_event_only
        else:
            on_event = None

    progress.on_stage_start("running_pipeline")
    progress.on_log(f"Running modules: {', '.join(filtered)}", level="info")
    if snapshot is not None:
        logs: list = snapshot.get("recent_logs", [])  # type: ignore[assignment]
        import datetime as _dt

        ts = _dt.datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{ts}] Running modules: {', '.join(filtered)}")
        if len(logs) > 100:
            logs = logs[-100:]
        snapshot["recent_logs"] = logs

    # Attach a SnapshotLogHandler so transcriptx logger output (INFO/WARNING/ERROR)
    # from the pipeline and analysis modules flows into the snapshot's recent_logs.
    # Only attached when we have a snapshot (i.e. a web GUI run).
    _tx_logger = logging.getLogger("transcriptx")
    _log_handler: Optional[SnapshotLogHandler] = None
    if snapshot is not None:
        # Remove any pre-existing SnapshotLogHandler to avoid duplicate attachment.
        _tx_logger.handlers = [
            h for h in _tx_logger.handlers if not isinstance(h, SnapshotLogHandler)
        ]
        _log_handler = SnapshotLogHandler(snapshot)
        _tx_logger.addHandler(_log_handler)

    start = time.perf_counter()
    _pipeline_exception: Optional[Exception] = None
    results: dict = {}
    from transcriptx.core.analysis.llm_support.model_selection import (
        bind_llm_model_selection,
        reset_llm_model_selection,
    )
    from transcriptx.core.analysis.llm_custom_qa.resolve import (
        resolve_effective_custom_qa_questions,
    )
    from transcriptx.core.analysis.llm_custom_qa.questions_binding import (
        bind_custom_qa_questions,
        reset_custom_qa_questions,
    )

    _selection_token = bind_llm_model_selection(
        _coerce_llm_model_selection(request.llm_model_selection)
    )
    # Resolve/bind only when llm_custom_qa is selected — avoid failing unrelated runs.
    _qa_token = None
    if "llm_custom_qa" in (filtered or []):
        _qa_effective = resolve_effective_custom_qa_questions(
            request_questions=request.llm_custom_qa_questions,
            request_field_present=True,
        )
        _qa_token = bind_custom_qa_questions(_qa_effective)
    try:
        manifest = RunManifestInput.from_cli_kwargs(
            transcript_file=path,
            mode=request.mode,
            modules=filtered,
            profile=request.profile,
            skip_confirm=True,
            output_dir=output_dir_str,
            include_unidentified_speakers=request.include_unidentified_speakers,
            persist=request.persist,
        )
        results = run_analysis_pipeline(manifest=manifest, on_event=on_event)
    except Exception as e:
        _pipeline_exception = e
    finally:
        if _qa_token is not None:
            reset_custom_qa_questions(_qa_token)
        reset_llm_model_selection(_selection_token)
        if _log_handler is not None:
            _tx_logger.removeHandler(_log_handler)
            _log_handler.close()
        if output_config is not None:
            output_config.output.base_output_dir = previous_base_output_dir

    if _pipeline_exception is not None:
        duration = time.perf_counter() - start
        progress.on_stage_complete("running_pipeline")
        if snapshot is not None:
            snapshot.update(
                status="failed",
                phase="failed",
                error=str(_pipeline_exception),
                latest_event=f"Pipeline error: {_pipeline_exception}",
            )
        return AnalysisResult(
            success=False,
            run_dir=Path(),
            manifest_path=Path(),
            modules_executed=[],
            warnings=[],
            errors=[str(_pipeline_exception)],
            duration_seconds=duration,
            status="failed",
        )

    # Prefer orchestrator wall-clock (same timer as run_performance.json).
    pipeline_duration = results.get("duration")
    if isinstance(pipeline_duration, (int, float)):
        duration = float(pipeline_duration)
    else:
        duration = time.perf_counter() - start
    progress.on_stage_complete("running_pipeline")

    # -----------------------------------------------------------------------
    # Finalizing phase
    # -----------------------------------------------------------------------
    _update_snapshot(snapshot, phase="finalizing", latest_event="Finalizing outputs…")

    output_dir = results.get("output_dir", "")
    output_path = Path(output_dir) if output_dir else Path()
    manifest_path = output_path / "manifest.json" if output_path else Path()
    modules_run = results.get("modules_run", [])
    result_errors = results.get("errors", [])

    if output_path and getattr(request, "analysis_preset", None):
        from transcriptx.core.pipeline.manifest_builder import record_analysis_preset

        record_analysis_preset(output_path, request.analysis_preset)

    status = "completed"
    if result_errors:
        status = "partial" if modules_run else "failed"

    if snapshot is not None:
        final_status = "failed" if status == "failed" else "completed"
        final_phase = "failed" if status == "failed" else "completed"
        snapshot.update(
            status=final_status,
            phase=final_phase,
            pct=100.0,
            latest_event=(
                f"Done: {len(modules_run)} modules run"
                + (f", {len(result_errors)} error(s)" if result_errors else "")
            ),
            error=(
                result_errors[0]
                if result_errors and status == "failed"
                else snapshot.get("error")
            ),
        )

    return AnalysisResult(
        success=len(result_errors) == 0 or len(modules_run) > 0,
        run_dir=output_path,
        manifest_path=manifest_path if manifest_path.exists() else Path(),
        modules_executed=modules_run,
        warnings=[],
        errors=result_errors,
        duration_seconds=duration,
        status=status,
    )


def validate_group_analysis_readiness(request: GroupAnalysisRequest) -> list[str]:
    """
    Pre-run validation for group analysis. Returns list of error messages; empty if ready.
    """
    errors: list[str] = []
    config = get_config()

    if not getattr(config.group_analysis, "enabled", False):
        errors.append("Group analysis must be enabled in config.")
        return errors

    try:
        target = GroupRef(path=request.group_uuid)
        scope, members = resolve_analysis_target(target)
    except (ValueError, TypeError) as e:
        errors.append(str(e))
        return errors

    if not members:
        errors.append("Group has no members.")
        return errors

    resolved_paths: list[str] = []
    missing_paths: list[str] = []
    for member in members:
        path = getattr(member, "file_path", None)
        if not path:
            continue
        p = Path(path)
        if p.exists():
            resolved_paths.append(str(p))
        else:
            missing_paths.append(path)

    if not resolved_paths:
        errors.append(
            "No member transcript paths exist on disk. "
            "Check that transcript files are available (e.g. in Docker mounts)."
        )
        return errors

    if request.mode not in ("quick", "full"):
        errors.append(f"Invalid mode: {request.mode}. Must be 'quick' or 'full'")
    valid_profiles = (
        "balanced",
        "academic",
        "business",
        "casual",
        "technical",
        "interview",
    )
    if request.profile and request.profile not in valid_profiles:
        errors.append(f"Invalid profile: {request.profile}")
    if request.modules is not None:
        available = get_available_modules()
        invalid = [m for m in request.modules if m not in available]
        if invalid:
            errors.append(f"Invalid modules: {', '.join(invalid)}")
        unsupported = _modules_unsupported_for_group(
            [m for m in request.modules if m in available]
        )
        if unsupported:
            errors.append(
                "Modules not supported for group analysis: " + ", ".join(unsupported)
            )
    _append_llm_model_selection_errors(request, errors)
    return errors


def _format_aggregation_warning_message(w: Any) -> str:
    """Single-line message for Studio / logs from structured aggregation warning dict."""
    if isinstance(w, dict):
        code = w.get("code") or "WARNING"
        msg = w.get("message") or ""
        ak = w.get("aggregation_key")
        extra = f" [{ak}]" if ak else ""
        return f"{code}{extra}: {msg}"
    return str(w)


def run_group_analysis(
    request: GroupAnalysisRequest,
    progress: ProgressCallback | None = None,
    snapshot: Optional[MutableMapping[str, Any]] = None,
) -> AnalysisResult:
    """
    Run group-level analysis (all members + aggregation). No prompts, no prints.
    """
    if progress is None:
        progress = NullProgress()

    validation = _validate_or_fail(snapshot, request, validate_group_analysis_readiness)
    if not validation.valid:
        assert validation.result is not None
        return validation.result

    target = GroupRef(path=request.group_uuid)
    try:
        scope, members = resolve_analysis_target(target)
    except (ValueError, TypeError) as e:
        _update_snapshot(snapshot, status="failed", phase="failed", error=str(e))
        return _failure_result([str(e)])

    resolved_paths = [m.file_path for m in members if getattr(m, "file_path", None)]
    missing = [p for p in resolved_paths if not Path(p).exists()]
    warnings: list[str] = []
    if missing:
        warnings.append(
            f"{len(missing)} of {len(resolved_paths)} member paths missing; "
            "analysis may be incomplete."
        )
        resolved_paths = [p for p in resolved_paths if Path(p).exists()]
    if not resolved_paths:
        _update_snapshot(
            snapshot,
            status="failed",
            phase="failed",
            error="No member paths exist on disk.",
        )
        return _failure_result(["No member transcript paths exist on disk."])

    selected, module_error = _resolve_modules(
        request.modules, resolved_paths, for_group=True
    )
    if module_error:
        _update_snapshot(snapshot, status="failed", phase="failed", error=module_error)
        return _failure_result([module_error])

    apply_analysis_mode_settings(request.mode, request.profile)
    filtered = filter_modules_by_mode(selected, request.mode)

    if snapshot is not None:
        snap = snapshot
        snap.update(
            status="running",
            phase="running_pipeline",
            total=len(filtered) * len(resolved_paths),
            completed=0,
            skipped=0,
            failed=0,
            pct=0.0,
            latest_event=f"Running group analysis on {len(resolved_paths)} transcripts…",
            error=None,
        )
        if "recent_logs" not in snap:
            snap["recent_logs"] = []

    progress.on_stage_start("validating")
    progress.on_stage_complete("validating")
    progress.on_stage_start("running_pipeline")
    progress.on_log(
        f"Running group analysis: {len(resolved_paths)} transcripts, "
        f"modules: {', '.join(filtered)}",
        level="info",
    )
    if snapshot is not None:
        import datetime as _dt

        logs: list = snapshot.get("recent_logs", [])
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        logs.append(
            f"[{ts}] Running group analysis on {len(resolved_paths)} transcripts: "
            f"{', '.join(filtered)}"
        )
        if len(logs) > 100:
            logs = logs[-100:]
        snapshot["recent_logs"] = logs

    _tx_logger = logging.getLogger("transcriptx")
    _log_handler: Optional[SnapshotLogHandler] = None
    if snapshot is not None:
        _tx_logger.handlers = [
            h for h in _tx_logger.handlers if not isinstance(h, SnapshotLogHandler)
        ]
        _log_handler = SnapshotLogHandler(snapshot)
        _tx_logger.addHandler(_log_handler)

    start = time.perf_counter()
    _pipeline_exception: Optional[Exception] = None
    results: dict = {}
    from transcriptx.core.analysis.llm_support.model_selection import (
        bind_llm_model_selection,
        reset_llm_model_selection,
    )
    from transcriptx.core.analysis.llm_custom_qa.resolve import (
        resolve_effective_custom_qa_questions,
    )
    from transcriptx.core.analysis.llm_custom_qa.questions_binding import (
        bind_custom_qa_questions,
        reset_custom_qa_questions,
    )

    _selection_token = bind_llm_model_selection(
        _coerce_llm_model_selection(request.llm_model_selection)
    )
    _qa_token = None
    if "llm_custom_qa" in (filtered or []):
        _qa_effective = resolve_effective_custom_qa_questions(
            request_questions=request.llm_custom_qa_questions,
            request_field_present=True,
        )
        _qa_token = bind_custom_qa_questions(_qa_effective)
    try:
        results = run_analysis_pipeline(
            target=target,
            selected_modules=filtered,
            speaker_options=SpeakerRunOptions(
                include_unidentified=request.include_unidentified_speakers
            ),
            persist=request.persist,
            on_event=None,
        )
    except Exception as e:
        _pipeline_exception = e
    finally:
        if _qa_token is not None:
            reset_custom_qa_questions(_qa_token)
        reset_llm_model_selection(_selection_token)
        if _log_handler is not None:
            _tx_logger.removeHandler(_log_handler)
            _log_handler.close()

    if _pipeline_exception is not None:
        duration = time.perf_counter() - start
        progress.on_stage_complete("running_pipeline")
        if snapshot is not None:
            snapshot.update(
                status="failed",
                phase="failed",
                error=str(_pipeline_exception),
                latest_event=f"Pipeline error: {_pipeline_exception}",
            )
        return AnalysisResult(
            success=False,
            run_dir=Path(),
            manifest_path=Path(),
            modules_executed=[],
            warnings=warnings,
            errors=[str(_pipeline_exception)],
            duration_seconds=duration,
            status="failed",
        )

    duration = time.perf_counter() - start
    progress.on_stage_complete("running_pipeline")

    group_output_dir = results.get("group_output_dir", "")
    output_path = Path(group_output_dir) if group_output_dir else Path()
    manifest_path = output_path / "manifest.json" if output_path else Path()
    group_errors = results.get("errors", [])
    modules_executed = results.get("modules_run", filtered)
    if output_path and getattr(request, "analysis_preset", None):
        from transcriptx.core.pipeline.manifest_builder import record_analysis_preset

        record_analysis_preset(output_path, request.analysis_preset)
    if output_path and output_path.exists():
        try:
            group_truth = project_group_outcomes(output_path)
            modules_executed = [
                r.module_id
                for r in group_truth.group_outcomes
                if r.status == "succeeded"
            ]
            status_map = {
                "succeeded": "completed",
                "partial": "partial",
                "failed": "failed",
                "blocked": "failed",
                "skipped": "failed",
            }
            status = status_map[group_truth.status]
        except Exception:
            status = results.get("status", "completed")
    else:
        status = results.get("status", "completed")
    if not modules_executed:
        modules_executed = filtered
    if group_errors and status == "completed":
        status = "partial"

    raw_agg = results.get("aggregation_warnings")
    aggregation_warnings: List[Any] = list(raw_agg) if isinstance(raw_agg, list) else []
    chart_failed = sum(
        1
        for w in aggregation_warnings
        if isinstance(w, dict) and w.get("code") == "GROUP_CHART_FAILED"
    )
    merged_warnings = list(warnings)
    if chart_failed:
        merged_warnings.append(
            f"Group chart generation failed for {chart_failed} aggregation(s); "
            "see Aggregation notices below."
        )
    for w in aggregation_warnings:
        if isinstance(w, dict) and w.get("code") == "GROUP_CHART_FAILED":
            merged_warnings.append(_format_aggregation_warning_message(w))

    if snapshot is not None:
        final_status = "failed" if status == "failed" else "completed"
        final_phase = "failed" if status == "failed" else "completed"
        latest = f"Done: group analysis on {len(resolved_paths)} transcripts" + (
            f", {len(group_errors)} error(s)" if group_errors else ""
        )
        if chart_failed:
            latest += f", {chart_failed} group chart failure(s)"
        snapshot.update(
            status=final_status,
            phase=final_phase,
            pct=100.0,
            latest_event=latest,
            error=(
                group_errors[0]
                if group_errors and status == "failed"
                else snapshot.get("error")
            ),
        )

    return AnalysisResult(
        success=len(group_errors) == 0 or status in ("completed", "partial"),
        run_dir=output_path,
        manifest_path=manifest_path if manifest_path.exists() else Path(),
        modules_executed=modules_executed,
        warnings=merged_warnings,
        errors=group_errors,
        duration_seconds=duration,
        status=status,
        aggregation_warnings=aggregation_warnings,
    )
