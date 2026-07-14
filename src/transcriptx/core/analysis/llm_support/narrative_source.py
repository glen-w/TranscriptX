"""Narrative-summary source resolution: deterministic summary as LLM input.

Lazy imports of manifest-loader and outcome-projection helpers inside
``_load_registered_summary_path`` are intentional; hoisting them to module
scope can introduce startup import cycles with the pipeline package.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, cast

from transcriptx.core.analysis.llm_module_errors import (
    ModuleDependencyMissingError,
    ModuleEmptyInputError,
)

__all__ = [
    "summary_has_content",
    "resolve_summary_payload",
    "serialise_summary_input",
]

_SUMMARY_CANONICAL_TEMPLATE = "summary/data/global/{base}_summary.json"


def summary_has_content(summary_payload: Dict[str, Any]) -> bool:
    """Reuse the executive-summary no-signal predicate."""
    overview = summary_payload.get("overview", {})
    key_themes = summary_payload.get("key_themes", {}).get("bullets", [])
    tension_points = summary_payload.get("tension_points", {}).get("bullets", [])
    commitments = summary_payload.get("commitments", {}).get("items", [])
    return bool(
        overview.get("paragraph") or key_themes or tension_points or commitments
    )


def _canonical_summary_rel_path(base_name: str) -> str:
    return _SUMMARY_CANONICAL_TEMPLATE.format(base=base_name)


def _load_registered_summary_path(
    transcript_dir: Path,
    base_name: str,
) -> Optional[Path]:
    """Return summary JSON path only when registered for the current run."""
    canonical_rel = _canonical_summary_rel_path(base_name)
    canonical_path = transcript_dir / canonical_rel

    meta_path = transcript_dir / ".transcriptx" / "artifacts_meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if isinstance(meta, dict) and canonical_rel in meta:
                if canonical_path.exists():
                    return canonical_path
        except (OSError, json.JSONDecodeError):
            pass

    manifest_path = transcript_dir / "manifest.json"
    if manifest_path.exists():
        try:
            from transcriptx.core.pipeline.manifest_loader import load_artifact_manifest

            manifest = load_artifact_manifest(manifest_path)
            artifacts = manifest.get("artifacts") or []
            registered = {
                a.get("rel_path")
                for a in artifacts
                if isinstance(a, dict) and a.get("module") == "summary"
            }
            if canonical_rel in registered and canonical_path.exists():
                return canonical_path
        except Exception:
            pass

    run_results_path = transcript_dir / "run_results.json"
    if run_results_path.exists():
        try:
            from transcriptx.core.pipeline.manifest_loader import load_run_results
            from transcriptx.core.pipeline.module_outcomes import (
                project_canonical_outcomes,
            )

            run_results = load_run_results(run_results_path)
            summary_row = next(
                (
                    row
                    for row in project_canonical_outcomes(run_results)
                    if row.get("module_id") == "summary"
                ),
                None,
            )
            if (
                summary_row
                and summary_row.get("execution_status") == "run"
                and canonical_path.exists()
            ):
                return canonical_path
        except Exception:
            pass

    return None


def resolve_summary_payload(context: Any) -> Dict[str, Any]:
    """
    Resolve deterministic summary input from pipeline context.

    Falls back to a registered current-run artifact only (no blind path lookup).
    """
    stored = context.get_analysis_result("summary")
    if isinstance(stored, dict):
        status = stored.get("status")
        if status == "error":
            raise ModuleDependencyMissingError(
                "Summary dependency failed in the current run",
                dependency="summary",
                state="failed",
            )
        if status == "skipped":
            raise ModuleDependencyMissingError(
                "Summary dependency was skipped in the current run",
                dependency="summary",
                state="skipped",
            )
        if status == "blocked":
            raise ModuleDependencyMissingError(
                "Summary dependency was blocked in the current run",
                dependency="summary",
                state="blocked",
            )
        payload = stored.get("payload") if "payload" in stored else stored
        if isinstance(payload, dict) and payload:
            if not summary_has_content(payload):
                raise ModuleEmptyInputError(
                    "Deterministic summary has no usable signal for narrative generation"
                )
            return payload

    base_name = context.get_base_name()
    artifact_path = _load_registered_summary_path(
        Path(context.get_transcript_dir()),
        base_name,
    )
    if artifact_path is not None:
        with open(artifact_path, encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict):
            if not summary_has_content(loaded):
                raise ModuleEmptyInputError(
                    "Deterministic summary has no usable signal for narrative generation"
                )
            return cast(Dict[str, Any], loaded)

    raise ModuleDependencyMissingError(
        "Summary dependency is missing from context and no resumable artifact was found",
        dependency="summary",
        state="missing",
    )


def serialise_summary_input(summary_payload: Dict[str, Any]) -> str:
    """Canonical serialisation of the structured summary input for hashing."""
    subset = {
        "overview": summary_payload.get("overview", {}),
        "key_themes": summary_payload.get("key_themes", {}),
        "tension_points": summary_payload.get("tension_points", {}),
        "commitments": summary_payload.get("commitments", {}),
    }
    return json.dumps(subset, sort_keys=True, separators=(",", ":"), default=str)
