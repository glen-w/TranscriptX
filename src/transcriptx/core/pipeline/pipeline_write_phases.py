"""
Write-side phases for pipeline persistence.

Ordering contract:
1) normalize and persist canonical outcomes (`run_results.json`)
2) persist artifact manifest (`manifest.json`)
3) emit secondary summaries/reporting views
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from transcriptx.core.pipeline.dag_pipeline_progress import (
    module_completed_event,
    module_failed_event,
    module_skipped_event,
    module_started_event,
    run_completed_event,
)
from transcriptx.core.pipeline.manifest_builder import (
    write_output_manifest,
    write_run_results_summary,
)

ProgressEmit = Callable[[Dict[str, Any]], None]


def build_preset_explanation(modules_run: List[str], skipped_modules: List[Any]) -> str:
    """Build a short human-readable explanation of what ran and what was skipped."""
    included = ", ".join(modules_run) if modules_run else "none"
    parts = []
    for entry in skipped_modules or []:
        if isinstance(entry, dict) and "module" in entry:
            reason = entry.get("reason", "Skipped")
            parts.append(f"{entry['module']} ({reason})")
        elif isinstance(entry, str):
            parts.append(f"{entry} (not in registry)")
    excluded = "; ".join(parts) if parts else "none"
    return f"Included: {included}. Excluded: {excluded}."


def persist_canonical_run_outcomes(
    *,
    run_dir: Path,
    run_id: str,
    transcript_key: str,
    modules_enabled: List[str],
    modules_run: List[str],
    skipped_modules: List[Any],
    errors: List[str],
    module_results: Optional[Dict[str, Any]] = None,
    terminal_outcomes: Optional[Dict[str, Any]] = None,
    pipeline_status: Optional[str] = None,
    run_status: Optional[str] = None,
) -> Path:
    """Persist canonical normalized run outcomes to run_results.json."""
    return write_run_results_summary(
        run_dir=run_dir,
        run_id=run_id,
        transcript_key=transcript_key,
        modules_enabled=modules_enabled,
        modules_run=modules_run,
        skipped_modules=skipped_modules,
        errors=errors,
        preset_explanation=build_preset_explanation(modules_run, skipped_modules),
        module_results=module_results,
        terminal_outcomes=terminal_outcomes,
        pipeline_status=pipeline_status,
        run_status=run_status,
    )


def _safe_emit(on_event: Optional[ProgressEmit], event: Dict[str, Any]) -> None:
    if on_event is None:
        return
    try:
        on_event(event)
    except Exception:
        pass


def _progress_counts(results: Dict[str, Any]) -> Dict[str, int]:
    raw = results.get("progress_counts") or {}
    return {
        "completed": int(raw.get("completed", 0) or 0),
        "skipped": int(raw.get("skipped", 0) or 0),
        "failed": int(raw.get("failed", 0) or 0),
        "total": int(raw.get("total", 0) or 0),
    }


def _emit_finalize_module_started(
    *,
    on_event: Optional[ProgressEmit],
    module_id: str,
    index: int,
    counts: Dict[str, int],
) -> None:
    event = module_started_event(
        module_name=module_id,
        index=index,
        total_modules=counts["total"],
        ev_completed=counts["completed"],
        ev_skipped=counts["skipped"],
        ev_failed=counts["failed"],
    )
    event["phase"] = "finalizing"
    _safe_emit(on_event, event)


def _emit_finalize_module_outcome(
    *,
    on_event: Optional[ProgressEmit],
    module_id: str,
    index: int,
    counts: Dict[str, int],
    status: str,
    skip_reason: str | None = None,
    error: str | None = None,
    duration_ms: float | None = None,
) -> Dict[str, int]:
    """Emit completed/skipped/failed for one finalize module; return updated counts."""
    updated = dict(counts)
    phase = "finalizing"
    if status == "skipped":
        updated["skipped"] = updated["skipped"] + 1
        event = module_skipped_event(
            module_name=module_id,
            index=index,
            total_modules=updated["total"],
            ev_completed=updated["completed"],
            ev_skipped=updated["skipped"],
            ev_failed=updated["failed"],
            message=skip_reason or "finalize_phase",
        )
    elif status == "failed":
        updated["failed"] = updated["failed"] + 1
        event = module_failed_event(
            module_name=module_id,
            index=index,
            total_modules=updated["total"],
            ev_completed=updated["completed"],
            ev_skipped=updated["skipped"],
            ev_failed=updated["failed"],
            error=error or "finalize_phase_failed",
        )
    else:
        updated["completed"] = updated["completed"] + 1
        event = module_completed_event(
            module_name=module_id,
            index=index,
            total_modules=updated["total"],
            ev_completed=updated["completed"],
            ev_skipped=updated["skipped"],
            ev_failed=updated["failed"],
            duration_ms=float(duration_ms or 0.0),
        )
    event["phase"] = phase
    _safe_emit(on_event, event)
    return updated


def _finish_deferred_run_completed(
    *,
    on_event: Optional[ProgressEmit],
    results: Dict[str, Any],
    counts: Dict[str, int],
) -> None:
    message = (
        f"Pipeline complete: {counts['completed']} run, "
        f"{counts['skipped']} skipped, {counts['failed']} failed"
    )
    _safe_emit(
        on_event,
        run_completed_event(
            total_modules=counts["total"],
            ev_completed=counts["completed"],
            ev_skipped=counts["skipped"],
            ev_failed=counts["failed"],
            message=message,
        ),
    )
    results["defer_run_completed"] = False
    results["progress_counts"] = dict(counts)


def persist_canonical_results_and_artifacts(
    *,
    run_dir: Path,
    run_id: str,
    transcript_key: str,
    modules_enabled: List[str],
    results: Dict[str, Any],
    config: Optional[Any] = None,
    on_event: Optional[ProgressEmit] = None,
) -> Dict[str, Optional[Path]]:
    """
    Persist canonical run outcomes first, then finalize-phase publishers + manifest.
    Returns written paths for diagnostics.

    When the DAG deferred ``run_completed`` (finalize modules selected), this
    function emits finalize-module progress events and the terminal
    ``run_completed`` so the GUI stays on Finalizing until chart descriptions
    (and peers) finish.
    """
    skipped = list(results.get("skipped_modules", []))
    modules_run = list(results.get("modules_run", []))
    errors = list(results.get("errors", []))
    pending_finalize_ids = [
        str(m)
        for m in (results.get("pending_finalize_modules") or [])
        if str(m).strip()
    ]
    finish_terminal = bool(results.get("defer_run_completed"))
    counts = _progress_counts(results)
    if finish_terminal and counts["total"] <= 0:
        counts["total"] = len(modules_run) + len(pending_finalize_ids)

    # Finalize-phase modules (e.g. chart_descriptions) run after this first write.
    # Mark them pending so observers do not see a false modules_failed projection.
    try:
        from transcriptx.core.pipeline.module_registry import get_module_info

        pending_finalize = []
        for mid in modules_enabled:
            info = get_module_info(mid)
            if info is None or not bool(getattr(info, "finalize_phase", False)):
                continue
            if mid in modules_run:
                continue
            pending_finalize.append({"module": mid, "reason": "pending_finalize"})
            if mid not in pending_finalize_ids:
                pending_finalize_ids.append(mid)
        if pending_finalize:
            skipped = list(skipped) + pending_finalize
    except Exception:
        pass

    run_results_path = persist_canonical_run_outcomes(
        run_dir=run_dir,
        run_id=run_id,
        transcript_key=transcript_key,
        modules_enabled=modules_enabled,
        modules_run=modules_run,
        skipped_modules=skipped,
        errors=errors,
        module_results=dict(results.get("module_results", {})),
        terminal_outcomes=dict(results.get("terminal_outcomes", {})),
        pipeline_status=(
            str(results["status"]) if results.get("status") is not None else None
        ),
    )

    dag_done = counts["completed"] + counts["skipped"] + counts["failed"]
    if finish_terminal:
        for offset, mid in enumerate(pending_finalize_ids):
            _emit_finalize_module_started(
                on_event=on_event,
                module_id=mid,
                index=dag_done + offset + 1,
                counts=counts,
            )

    try:
        from transcriptx.core.analysis.chart_descriptions.coordinator import (
            run_finalization_coordinator,
        )
        from transcriptx.core.utils.config import get_config

        cfg = config or get_config()
        fin = run_finalization_coordinator(
            run_dir=run_dir,
            run_id=run_id,
            transcript_key=transcript_key,
            selected_modules=list(modules_enabled),
            modules_enabled=list(modules_enabled),
            config=cfg,
            run_kind="transcript",
            run_group_synthesis=False,
        )
        if fin.module_results:
            results.setdefault("module_results", {}).update(fin.module_results)
            # Drop provisional pending_finalize placeholders once finalize has spoken.
            skipped = [
                s
                for s in skipped
                if not (isinstance(s, dict) and s.get("reason") == "pending_finalize")
            ]
            for mid, mres in fin.module_results.items():
                mid_s = str(mid)
                status = str((mres or {}).get("status") or "")
                if mid_s in modules_run:
                    continue
                if status == "skipped":
                    skipped.append(
                        {
                            "module": mid_s,
                            "reason": str(
                                (mres or {}).get("skip_reason") or "finalize_phase"
                            ),
                        }
                    )
                else:
                    # Finalize-phase modules run outside the DAG; record them as
                    # executed so they are not projected as modules_failed.
                    modules_run.append(mid_s)
            results["modules_run"] = list(modules_run)
            results["skipped_modules"] = list(skipped)
            # Re-persist outcomes so finalize-phase metrics appear
            run_results_path = persist_canonical_run_outcomes(
                run_dir=run_dir,
                run_id=run_id,
                transcript_key=transcript_key,
                modules_enabled=modules_enabled,
                modules_run=modules_run,
                skipped_modules=skipped,
                errors=errors,
                module_results=dict(results.get("module_results", {})),
                terminal_outcomes=dict(results.get("terminal_outcomes", {})),
                pipeline_status=(
                    str(results["status"])
                    if results.get("status") is not None
                    else None
                ),
            )
        manifest_path = fin.manifest_path

        if finish_terminal:
            for offset, mid in enumerate(pending_finalize_ids):
                module_results = fin.module_results or {}
                if mid not in module_results:
                    counts = _emit_finalize_module_outcome(
                        on_event=on_event,
                        module_id=mid,
                        index=dag_done + offset + 1,
                        counts=counts,
                        status="skipped",
                        skip_reason="finalize_no_result",
                    )
                    continue
                mres = module_results.get(mid) or {}
                status = str(mres.get("status") or "")
                duration_ms = mres.get("duration_ms")
                if status == "skipped":
                    counts = _emit_finalize_module_outcome(
                        on_event=on_event,
                        module_id=mid,
                        index=dag_done + offset + 1,
                        counts=counts,
                        status="skipped",
                        skip_reason=str(mres.get("skip_reason") or "finalize_phase"),
                    )
                elif status in {"failed", "error"}:
                    err = mres.get("error")
                    err_msg = None
                    if isinstance(err, dict):
                        err_msg = str(err.get("message") or err.get("error_code") or "")
                    elif err:
                        err_msg = str(err)
                    counts = _emit_finalize_module_outcome(
                        on_event=on_event,
                        module_id=mid,
                        index=dag_done + offset + 1,
                        counts=counts,
                        status="failed",
                        error=err_msg or "finalize_phase_failed",
                        duration_ms=(
                            float(duration_ms) if duration_ms is not None else None
                        ),
                    )
                else:
                    # success / published → completed
                    counts = _emit_finalize_module_outcome(
                        on_event=on_event,
                        module_id=mid,
                        index=dag_done + offset + 1,
                        counts=counts,
                        status="success",
                        duration_ms=(
                            float(duration_ms) if duration_ms is not None else None
                        ),
                    )
            _finish_deferred_run_completed(
                on_event=on_event, results=results, counts=counts
            )
    except Exception:
        from transcriptx.core.utils.logger import get_logger

        get_logger().exception(
            "run finalization coordinator failed; writing base manifest"
        )
        manifest_path = write_output_manifest(
            run_dir=run_dir,
            run_id=run_id,
            transcript_key=transcript_key,
            modules_enabled=modules_enabled,
        )
        if finish_terminal:
            for offset, mid in enumerate(pending_finalize_ids):
                counts = _emit_finalize_module_outcome(
                    on_event=on_event,
                    module_id=mid,
                    index=dag_done + offset + 1,
                    counts=counts,
                    status="failed",
                    error="finalize_coordinator_failed",
                )
            _finish_deferred_run_completed(
                on_event=on_event, results=results, counts=counts
            )

    return {
        "run_results_path": run_results_path,
        "manifest_path": manifest_path,
    }
