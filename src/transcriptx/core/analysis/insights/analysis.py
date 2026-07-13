"""Content-first insights module."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.phrase_quality import (
    PHRASE_QUALITY_VERSION,
    resource_fingerprint,
)


def _top_phrases(eligibility: Dict[str, Any], limit: int = 8) -> List[Dict[str, Any]]:
    phrases = eligibility.get("content_phrases") or []
    if not isinstance(phrases, list):
        return []
    rows = [row for row in phrases if isinstance(row, dict) and row.get("phrase")]
    rows.sort(
        key=lambda row: (
            -float((row.get("score") or {}).get("total", 0.0)),
            str(row.get("phrase")),
        )
    )
    return rows[:limit]


def _recurring_ideas(
    eligibility: Dict[str, Any], limit: int = 8
) -> List[Dict[str, Any]]:
    score_map = eligibility.get("phrase_scores") or {}
    rows = []
    if not isinstance(score_map, dict):
        return rows
    for phrase, score in score_map.items():
        if not isinstance(score, dict):
            continue
        if float(score.get("recurrence", 0.0)) <= 0.0:
            continue
        rows.append({"phrase": phrase, "score": score})
    rows.sort(
        key=lambda row: (
            -float((row.get("score") or {}).get("recurrence", 0.0)),
            -float((row.get("score") or {}).get("total", 0.0)),
            str(row.get("phrase")),
        )
    )
    return rows[:limit]


class InsightsAnalysis(AnalysisModule):
    """Compose key themes and style markers from upstream analysis outputs."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "insights"

    def run_from_context(self, context):
        self._context = context
        try:
            return super().run_from_context(context)
        finally:
            self._context = None

    def analyze(
        self,
        segments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        context = getattr(self, "_context", None)
        eligibility = (
            context.get_analysis_result("insight_eligibility")
            if context is not None
            else {}
        ) or {}
        highlights = (
            context.get_analysis_result("highlights") if context is not None else {}
        ) or {}
        tics = context.get_analysis_result("tics") if context is not None else {}

        key_themes = _top_phrases(eligibility)
        recurring_ideas = _recurring_ideas(eligibility)
        style_markers = {
            "tics": (tics or {}).get("speaker_stats", {}),
            "global_tics": (tics or {}).get("global_stats", {}),
        }
        notable_moments = (
            ((highlights.get("sections") or {}).get("cold_open") or {}).get("items")
            or []
        )[:8]

        return {
            "schema_version": 2,
            "phrase_quality_version": PHRASE_QUALITY_VERSION,
            "phrase_quality_resource_fingerprint": resource_fingerprint(),
            "key_themes": key_themes,
            "recurring_ideas": recurring_ideas,
            "style_markers": style_markers,
            "notable_moments": notable_moments,
        }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        output_service.save_data(results, "insights", format_type="json")
