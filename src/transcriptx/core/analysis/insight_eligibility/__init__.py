"""Shared insight eligibility pipeline module."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.config import get_config

from .content_filter import filter_segments_for_insights
from .phrase_extraction import extract_content_phrases
from .windowing import build_rolling_windows, build_speaker_blocks


class InsightEligibilityAnalysis(AnalysisModule):
    """Build reusable content-vs-style eligibility artifacts for downstream modules."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "insight_eligibility"
        self._tics_result: Optional[Dict[str, Any]] = None

    def run_from_context(self, context: Any) -> Dict[str, Any]:
        self._tics_result = context.get_analysis_result("tics")
        try:
            return super().run_from_context(context)
        finally:
            self._tics_result = None

    def analyze(
        self,
        segments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        filtered_segments, tic_mask, tic_mask_sources = filter_segments_for_insights(
            segments, tics_result=self._tics_result
        )
        windows = build_rolling_windows(filtered_segments, window_size=5, stride=2)
        speaker_blocks = build_speaker_blocks(filtered_segments)
        elig_cfg = get_config().analysis.insight_eligibility
        phrases, phrase_scores = extract_content_phrases(
            filtered_segments,
            tic_mask=tic_mask,
            windows=windows,
            speaker_blocks=speaker_blocks,
            min_frequency=int(elig_cfg.min_frequency),
            min_score=float(elig_cfg.min_score),
            require_spread_or_recurrence_for_singletons=bool(
                elig_cfg.require_spread_or_recurrence_for_singletons
            ),
        )

        densities = {
            str(seg.segment_index): float(seg.content_density)
            for seg in filtered_segments
        }
        return {
            "schema_version": 2,
            "semantic_version": "insight_eligibility.v2",
            "group_reuse_policy": "recompute_per_run",
            "external_nondeterminism": [
                "spaCy model/version can affect tokenization/POS details",
                "scikit-learn vocabulary tie behavior may vary across versions",
            ],
            "filtered_segments": [seg.to_dict() for seg in filtered_segments],
            "tic_mask": sorted(tic_mask),
            "tic_mask_sources": tic_mask_sources,
            "windows": windows,
            "speaker_blocks": speaker_blocks,
            "content_phrases": phrases,
            "phrase_scores": phrase_scores,
            "content_densities": densities,
            "thresholds": {
                "min_score": float(elig_cfg.min_score),
                "min_frequency": int(elig_cfg.min_frequency),
                "require_spread_or_recurrence_for_singletons": bool(
                    elig_cfg.require_spread_or_recurrence_for_singletons
                ),
            },
        }

    def _save_results(
        self,
        results: Dict[str, Any],
        output_service: "OutputService",
    ) -> None:
        output_service.save_data(results, "insight_eligibility", format_type="json")
        output_service.save_data(
            {"tic_mask": results.get("tic_mask", [])},
            "insight_eligibility_tic_mask",
            format_type="json",
        )
        output_service.save_data(
            {"phrase_scores": results.get("phrase_scores", {})},
            "insight_eligibility_phrase_scores",
            format_type="json",
        )


__all__ = ["InsightEligibilityAnalysis"]
