"""
Prompt-free analysis workflow. No questionary, rich, click, or typer.

Accepts explicit AnalysisRequest, returns structured AnalysisResult.
Uses ProgressCallback for status updates. Caller is responsible for
output capture if wrapping legacy code that still prints.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Callable, MutableMapping, Optional

from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.models.results import AnalysisResult
from transcriptx.app.progress import (
    NullProgress,
    ProgressCallback,
    ProgressEvent,
    SnapshotLogHandler,
    update_snapshot_from_event,
)
from transcriptx.core import (
    get_available_modules,
    get_default_modules,
    run_analysis_pipeline,
)
from transcriptx.core.analysis.selection import (
    apply_analysis_mode_settings,
    filter_modules_by_mode,
)
from transcriptx.core.pipeline.run_schema import RunManifestInput
from transcriptx.core.utils.config import get_config


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
        if snapshot is not None:
            snapshot.update(
                status="failed",
                phase="failed",
                error=f"Transcript file not found: {path}",
            )
        return AnalysisResult(
            success=False,
            run_dir=Path(),
            manifest_path=Path(),
            modules_executed=[],
            warnings=[],
            errors=[f"Transcript file not found: {path}"],
            status="failed",
        )

    # -----------------------------------------------------------------------
    # Validation phase
    # -----------------------------------------------------------------------
    if snapshot is not None:
        snapshot.update(
            status="running", phase="validating", latest_event="Validating inputs…"
        )
    progress.on_stage_start("validating")

    errors = validate_analysis_readiness(request)
    if errors:
        progress.on_stage_complete("validating")
        if snapshot is not None:
            snapshot.update(
                status="failed",
                phase="failed",
                error="; ".join(errors),
                latest_event="Validation failed",
            )
        return AnalysisResult(
            success=False,
            run_dir=Path(),
            manifest_path=Path(),
            modules_executed=[],
            warnings=[],
            errors=errors,
            status="failed",
        )
    progress.on_stage_complete("validating")

    available = get_available_modules()
    default = get_default_modules([str(path)])
    if request.modules is None or (
        isinstance(request.modules, list) and len(request.modules) == 0
    ):
        selected = default
    elif (
        isinstance(request.modules, list)
        and len(request.modules) == 1
        and request.modules[0].lower() == "all"
    ):
        selected = default
    elif request.modules:
        invalid = [m for m in request.modules if m not in available]
        if invalid:
            err_msg = f"Invalid modules: {', '.join(invalid)}"
            if snapshot is not None:
                snapshot.update(
                    status="failed", phase="failed", error=err_msg, latest_event=err_msg
                )
            return AnalysisResult(
                success=False,
                run_dir=Path(),
                manifest_path=Path(),
                modules_executed=[],
                warnings=[],
                errors=[err_msg],
                status="failed",
            )
        selected = list(request.modules)
    else:
        selected = default

    apply_analysis_mode_settings(request.mode, request.profile)
    filtered = filter_modules_by_mode(selected, request.mode)

    output_dir_str: str | None = None
    if request.output_dir:
        output_dir_str = str(Path(request.output_dir))
        config = get_config()
        config.output.base_output_dir = output_dir_str

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
    try:
        manifest = RunManifestInput.from_cli_kwargs(
            transcript_file=path,
            mode=request.mode,
            modules=filtered,
            profile=request.profile,
            skip_confirm=True,
            output_dir=output_dir_str,
            include_unidentified_speakers=request.include_unidentified_speakers,
            skip_speaker_gate=request.skip_speaker_mapping,
            persist=request.persist,
        )
        results = run_analysis_pipeline(manifest=manifest, on_event=on_event)
    except Exception as e:
        _pipeline_exception = e
    finally:
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
            warnings=[],
            errors=[str(_pipeline_exception)],
            duration_seconds=duration,
            status="failed",
        )

    duration = time.perf_counter() - start
    progress.on_stage_complete("running_pipeline")

    # -----------------------------------------------------------------------
    # Finalizing phase
    # -----------------------------------------------------------------------
    if snapshot is not None:
        snapshot.update(phase="finalizing", latest_event="Finalizing outputs…")

    output_dir = results.get("output_dir", "")
    output_path = Path(output_dir) if output_dir else Path()
    manifest_path = output_path / "manifest.json" if output_path else Path()
    modules_run = results.get("modules_run", [])
    result_errors = results.get("errors", [])

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
