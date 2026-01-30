"""
AnalysisModule wrappers for semantic similarity analyzers.
"""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.module_result import build_module_result, now_iso
from transcriptx.core.utils.speaker_extraction import (
    extract_speaker_info,
    get_speaker_display_name,
)
from transcriptx.utils.text_utils import is_named_speaker

from .analyzers import SemanticSimilarityAnalyzer, AdvancedSemanticSimilarityAnalyzer


def _count_named_speakers(segments: List[Dict[str, Any]]) -> int:
    """Return the number of distinct identified (named) speakers in segments."""
    names = set()
    for seg in segments:
        info = extract_speaker_info(seg)
        if info is None:
            continue
        name = get_speaker_display_name(info.grouping_key, [seg], segments)
        if name and is_named_speaker(name):
            names.add(name)
    return len(names)


class SemanticSimilarityAnalysis(AnalysisModule):
    """Semantic similarity analysis module."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "semantic_similarity"
        self.analyzer = SemanticSimilarityAnalyzer(config)

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        import warnings

        if speaker_map is not None:
            warnings.warn(
                "speaker_map parameter is deprecated. Speaker identification now uses "
                "speaker_db_id from segments directly.",
                DeprecationWarning,
                stacklevel=2,
            )
        return self.analyzer.detect_repetitions(segments, None)

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        """Skip analysis when only one identified speaker (no cross-speaker comparison)."""
        from transcriptx.core.utils.logger import log_analysis_complete, log_analysis_start

        segments = context.get_segments()
        if _count_named_speakers(segments) <= 1:
            log_analysis_start(self.module_name, context.transcript_path)
            context.store_analysis_result(self.module_name, {})
            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=now_iso(),
                finished_at=now_iso(),
                artifacts=[],
                metrics={"skipped": True, "reason": "single_identified_speaker"},
                payload_type="analysis_results",
                payload={},
            )
        return super().run_from_context(context)

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        output_service.save_data(results, "semantic_similarity", format_type="json")

        base_name = output_service.base_name
        try:
            self.analyzer.create_visualizations(results, output_service, base_name)
        except Exception as exc:
            from transcriptx.core.utils.logger import log_warning

            log_warning("SEMANTIC", f"Failed to create visualizations: {exc}")

        global_stats = {
            "total_repetitions": results.get("total_repetitions", 0),
            "unique_patterns": results.get("unique_patterns", 0),
        }
        output_service.save_summary(global_stats, {}, analysis_metadata={})


class SemanticSimilarityAdvancedAnalysis(AnalysisModule):
    """Advanced semantic similarity analysis module."""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.module_name = "semantic_similarity_advanced"
        self.analyzer = AdvancedSemanticSimilarityAnalyzer(config)

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        return self.analyzer.detect_repetitions(segments, speaker_map, None)

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        """Skip analysis when only one identified speaker (no cross-speaker comparison)."""
        from transcriptx.core.utils.logger import log_analysis_complete, log_analysis_start

        segments = context.get_segments()
        if _count_named_speakers(segments) <= 1:
            log_analysis_start(self.module_name, context.transcript_path)
            context.store_analysis_result(self.module_name, {})
            log_analysis_complete(self.module_name, context.transcript_path)
            return build_module_result(
                module_name=self.module_name,
                status="success",
                started_at=now_iso(),
                finished_at=now_iso(),
                artifacts=[],
                metrics={"skipped": True, "reason": "single_identified_speaker"},
                payload_type="analysis_results",
                payload={},
            )
        return super().run_from_context(context)

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        output_service.save_data(
            results, "semantic_similarity_advanced", format_type="json"
        )

        base_name = output_service.base_name
        self.analyzer.create_visualizations(results, output_service, base_name)

        global_stats = {
            "total_repetitions": results.get("total_repetitions", 0),
            "unique_patterns": results.get("unique_patterns", 0),
        }
        output_service.save_summary(global_stats, {}, analysis_metadata={})
