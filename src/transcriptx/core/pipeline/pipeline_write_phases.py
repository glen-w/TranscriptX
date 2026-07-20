"""
Write-side phases for pipeline persistence.

Ordering contract:
1) normalize and persist canonical outcomes (`run_results.json`)
2) persist artifact manifest (`manifest.json`)
3) emit secondary summaries/reporting views
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.pipeline.manifest_builder import (
    write_output_manifest,
    write_run_results_summary,
)


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
    )


def persist_canonical_results_and_artifacts(
    *,
    run_dir: Path,
    run_id: str,
    transcript_key: str,
    modules_enabled: List[str],
    results: Dict[str, Any],
    config: Optional[Any] = None,
) -> Dict[str, Optional[Path]]:
    """
    Persist canonical run outcomes first, then finalize-phase publishers + manifest.
    Returns written paths for diagnostics.
    """
    skipped = list(results.get("skipped_modules", []))
    modules_run = list(results.get("modules_run", []))
    errors = list(results.get("errors", []))

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
                if not (
                    isinstance(s, dict) and s.get("reason") == "pending_finalize"
                )
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

    return {
        "run_results_path": run_results_path,
        "manifest_path": manifest_path,
    }
