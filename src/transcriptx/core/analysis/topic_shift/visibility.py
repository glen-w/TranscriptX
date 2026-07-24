"""Platform visibility for topic_shift deterministic artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from transcriptx.core.pipeline.manifest_loader import load_run_results
from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes

TopicShiftVisibility = Literal["show", "suppress_failed", "absent", "unknown"]


def topic_shift_module_dir(run_root: Path) -> Path:
    return Path(run_root) / "topic_shift"


def topic_shift_spans_path(run_root: Path) -> Path:
    return (
        topic_shift_module_dir(run_root) / "data" / "global" / "topic_shift.spans.json"
    )


def topic_shift_enrichment_path(run_root: Path) -> Path:
    return (
        topic_shift_module_dir(run_root)
        / "data"
        / "global"
        / "topic_shift.enrichment.json"
    )


def _module_status(
    run_root: Path,
    *,
    run_results: dict[str, Any] | None = None,
) -> str:
    rr = run_results
    if rr is None:
        path = Path(run_root) / "run_results.json"
        if not path.is_file():
            return "not_run"
        try:
            rr = load_run_results(path)
        except Exception:
            return "unknown"
    try:
        for row in project_canonical_outcomes(rr):
            if row.module_id == "topic_shift":
                if row.status in {"failed", "skipped", "blocked", "succeeded"}:
                    return str(row.status)
                return "unknown"
    except Exception:
        return "unknown"
    return "not_run"


def resolve_topic_shift_visibility(
    run_root: Path | None,
    *,
    run_results: dict[str, Any] | None = None,
) -> TopicShiftVisibility:
    """
    Whether topic_shift chapters/artifacts should surface on any UI.

    Failed pipeline execution suppresses prior ACTIVE for all surfaces.
    """
    if run_root is None:
        return "absent"
    outcome = _module_status(run_root, run_results=run_results)
    if outcome == "failed":
        return "suppress_failed"
    if outcome in {"not_run", "skipped", "blocked"}:
        return "absent"
    if outcome == "unknown":
        return "unknown"
    if not topic_shift_spans_path(run_root).is_file():
        return "absent"
    return "show"


def suppress_topic_shift_surface_artifacts(
    artifacts: list[Any],
    *,
    run_root: Path | None,
    run_results: dict[str, Any] | None = None,
) -> list[Any]:
    """Drop topic_shift artifacts when pipeline execution failed for this run."""
    if run_root is None:
        return list(artifacts)
    if (
        resolve_topic_shift_visibility(run_root, run_results=run_results)
        != "suppress_failed"
    ):
        return list(artifacts)
    out: list[Any] = []
    for art in artifacts:
        module = getattr(art, "module", None)
        if module is None and isinstance(art, dict):
            module = art.get("module")
        if str(module or "") == "topic_shift":
            continue
        rel = getattr(art, "rel_path", None)
        if rel is None and isinstance(art, dict):
            rel = art.get("rel_path")
        rel_s = str(rel or "")
        if rel_s.startswith("topic_shift/") or "/topic_shift/" in rel_s:
            continue
        out.append(art)
    return out
