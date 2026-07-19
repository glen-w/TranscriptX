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
) -> Dict[str, Optional[Path]]:
    """
    Persist canonical run outcomes first, then artifact manifest.
    Returns written paths for diagnostics.
    """
    skipped = list(results.get("skipped_modules", []))
    modules_run = list(results.get("modules_run", []))
    errors = list(results.get("errors", []))

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
