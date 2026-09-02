"""Transcript picker analysis-coverage status (no Streamlit)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes
from transcriptx.core.utils.paths import OUTPUTS_DIR

ANALYSIS_STATUS_NONE = "no analysis"
ANALYSIS_STATUS_PARTIAL = "partial analysis"
ANALYSIS_STATUS_COMPLETE = "analysis complete"
ANALYSIS_STATUS_IN_PROGRESS = "analysis in progress"

_COMPLETE_PRESET = "thorough"


@dataclass(frozen=True)
class AnalysisPickerStatusIndex:
    """Slug → status plus source-path → slug for path-based pickers."""

    by_slug: dict[str, str]
    path_to_slug: dict[str, str]

    def status_for(
        self,
        *,
        slug: str | None = None,
        path: str | Path | None = None,
    ) -> str:
        """Return picker status for a sidebar slug or a transcript path."""
        if slug:
            return self.by_slug.get(slug, ANALYSIS_STATUS_NONE)
        if path is None:
            return ANALYSIS_STATUS_NONE
        raw = str(path)
        try:
            resolved = str(Path(path).expanduser().resolve())
        except OSError:
            resolved = raw
        mapped = self.path_to_slug.get(resolved) or self.path_to_slug.get(raw)
        if mapped:
            return self.by_slug.get(mapped, ANALYSIS_STATUS_NONE)
        stem = Path(raw).stem
        return self.by_slug.get(stem, ANALYSIS_STATUS_NONE)


def format_with_analysis_status(name: str, status: str) -> str:
    """Render ``Name (status)`` for transcript pickers."""
    return f"{name} ({status})"


def run_execution_status(run_results: Mapping[str, Any]) -> str:
    """Mirror run-controller buckets: completed / partial / failed / running."""
    if str(run_results.get("run_status") or "").strip().lower() == "running":
        return "running"
    rows = project_canonical_outcomes(dict(run_results))
    statuses = {row.status for row in rows}
    if "failed" in statuses and "succeeded" not in statuses:
        return "failed"
    if "failed" in statuses or "blocked" in statuses or "enabled" in statuses:
        return "partial"
    return "completed"


def is_complete_analysis_run(run_results: Mapping[str, Any]) -> bool:
    """True when a Thorough run finished without mixed failure/block leftovers."""
    preset = str(run_results.get("analysis_preset") or "").strip().lower()
    if preset != _COMPLETE_PRESET:
        return False
    return run_execution_status(run_results) == "completed"


def path_to_slug_from_entries(entries: Iterable[Mapping[str, Any]]) -> dict[str, str]:
    """Map resolved ``source_path`` → slug from index rows."""
    mapping: dict[str, str] = {}
    for entry in entries:
        slug = entry.get("slug")
        source_path = entry.get("source_path")
        if not slug or not source_path:
            continue
        mapping[str(source_path)] = str(slug)
        try:
            mapping[str(Path(str(source_path)).expanduser().resolve())] = str(slug)
        except OSError:
            continue
    return mapping


def run_results_mtime_ns(
    session_names: Iterable[str],
    *,
    outputs_dir: str | Path | None = None,
) -> int:
    """Newest ``run_results.json`` mtime among viewable sessions (cache key)."""
    base = Path(outputs_dir or OUTPUTS_DIR)
    newest = 0
    for name in session_names:
        if "/" not in name:
            continue
        slug, run_id = name.split("/", 1)
        path = base / slug / run_id / "run_results.json"
        try:
            newest = max(newest, int(path.stat().st_mtime_ns))
        except OSError:
            continue
    return newest


def analysis_status_by_slug(
    session_names: Iterable[str],
    *,
    outputs_dir: str | Path | None = None,
) -> dict[str, str]:
    """Classify each slug that has at least one viewable run.

    Slugs with no viewable runs are omitted (callers treat missing as no analysis).
    """
    base = Path(outputs_dir or OUTPUTS_DIR)
    slugs_with_runs: set[str] = set()
    complete_slugs: set[str] = set()

    for name in session_names:
        if "/" not in name:
            continue
        slug, run_id = name.split("/", 1)
        slugs_with_runs.add(slug)
        if slug in complete_slugs:
            continue
        payload = _load_run_results_payload(base / slug / run_id)
        if payload is None:
            continue
        if is_complete_analysis_run(payload):
            complete_slugs.add(slug)

    return {
        slug: (
            ANALYSIS_STATUS_COMPLETE
            if slug in complete_slugs
            else ANALYSIS_STATUS_PARTIAL
        )
        for slug in slugs_with_runs
    }


def build_analysis_picker_status(
    session_names: Iterable[str],
    *,
    outputs_dir: str | Path | None = None,
    transcripts: Iterable[Mapping[str, Any]] | None = None,
) -> AnalysisPickerStatusIndex:
    """Assemble picker status plus path→slug lookup."""
    if transcripts is None:
        from transcriptx.core.utils.slug_manager import list_all_transcripts

        transcripts = list_all_transcripts()
    return AnalysisPickerStatusIndex(
        by_slug=analysis_status_by_slug(session_names, outputs_dir=outputs_dir),
        path_to_slug=path_to_slug_from_entries(transcripts),
    )


def _load_run_results_payload(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "run_results.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None
