"""
Analyzer implementations for semantic similarity modules.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import (
    log_analysis_error,
    log_error,
    log_info,
    log_warning,
)
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.utils.simple_progress import progress, log_progress
from transcriptx.core.utils.speaker_extraction import (
    extract_speaker_info,
    get_speaker_display_name,
)

from .analysis_integration import load_analysis_results
from .clustering import cluster_repetitions_advanced, cluster_repetitions_basic
from .embeddings import EmbeddingCache, get_text_embedding
from .models import SemanticModelManager
from .quality_scoring import AdvancedQualityScorer, BasicQualityScorer
from .repetition_detection import (
    detect_cross_speaker_repetitions_advanced,
    detect_cross_speaker_repetitions_basic,
    detect_speaker_repetitions_advanced,
    detect_speaker_repetitions_basic,
)
from .similarity import SemanticSimilarityCalculator
from .summary import (
    generate_repetition_summary_advanced,
    generate_repetition_summary_basic,
)
from .visualization import (
    create_visualizations_advanced,
    create_visualizations_basic,
)


@dataclass
class ComparisonState:
    comparison_count: int
    max_comparisons: int


class SemanticSimilarityAnalyzer:
    """Semantic similarity and repetition detection analyzer."""

    def __init__(self, config: Any | None = None):
        if config is None:
            self.config = get_config()
        elif isinstance(config, dict):
            self.config = get_config()
        elif isinstance(config, str):
            raise TypeError(
                f"config must be None, dict, or config object, got str: {config}"
            )
        else:
            self.config = config

        self.max_segments = getattr(
            self.config.analysis, "max_segments_for_semantic", 1000
        )
        self.max_comparisons = getattr(
            self.config.analysis, "max_semantic_comparisons", 50000
        )
        self.timeout_seconds = getattr(
            self.config.analysis, "semantic_timeout_seconds", 300
        )
        self.batch_size = getattr(self.config.analysis, "semantic_batch_size", 32)

        model_name = getattr(
            self.config.analysis,
            "semantic_model_name",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        self.model_manager = SemanticModelManager(
            config=self.config,
            model_name=model_name,
            log_tag="SEMANTIC",
            progress_context=progress,
            progress_logger=log_progress,
        )
        self.model_manager.initialize()
        self.embedding_cache = EmbeddingCache()
        self.similarity_calculator = SemanticSimilarityCalculator(
            self.model_manager, self.embedding_cache, "SEMANTIC"
        )
        self.quality_scorer = BasicQualityScorer(self.config, "SEMANTIC")
        self.comparison_state = ComparisonState(0, self.max_comparisons)

    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        self.comparison_state.comparison_count += 1
        if self.comparison_state.comparison_count > self.max_comparisons:
            log_error(
                "SEMANTIC",
                f"Exceeded maximum comparisons ({self.max_comparisons}), using TF-IDF fallback",
            )
            return self.similarity_calculator.tfidf_similarity(text1, text2)
        return self.similarity_calculator.calculate(text1, text2)

    def detect_repetitions(
        self, segments: list[dict[str, Any]], speaker_map: dict[str, str] | None = None
    ) -> dict[str, Any]:
        log_progress("Starting repetition detection")
        if len(segments) > self.max_segments:
            log_warning(
                "SEMANTIC",
                f"Too many segments ({len(segments)}), limiting to {self.max_segments}",
            )
            if getattr(self.config.analysis, "use_quality_filtering", True):
                segments = self.quality_scorer.filter_segments(
                    segments, self.max_segments
                )
            else:
                segments = segments[: self.max_segments]

        self.comparison_state = ComparisonState(0, self.max_comparisons)

        try:
            speaker_segments: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for segment in segments:
                speaker_info = extract_speaker_info(segment)
                if speaker_info is None:
                    continue
                speaker = get_speaker_display_name(
                    speaker_info.grouping_key, [segment], segments
                )
                if not speaker or not is_named_speaker(speaker):
                    continue
                speaker_segments[speaker].append(segment)

            results = {
                "repetitions": [],
                "speaker_repetitions": {},
                "cross_speaker_repetitions": [],
                "repetition_clusters": [],
                "summary": {},
                "performance_metrics": {
                    "segments_processed": len(segments),
                    "comparisons_made": 0,
                    "timeout_reached": False,
                    "max_comparisons_exceeded": False,
                },
            }

            for speaker, segments_list in speaker_segments.items():
                if self.comparison_state.comparison_count > self.max_comparisons:
                    log_warning(
                        "SEMANTIC", "Stopping due to maximum comparisons reached"
                    )
                    results["performance_metrics"]["max_comparisons_exceeded"] = True
                    break

                speaker_reps = detect_speaker_repetitions_basic(
                    speaker=speaker,
                    segments=segments_list,
                    similarity_fn=self.calculate_semantic_similarity,
                    comparison_state=self.comparison_state,
                    similarity_threshold=getattr(
                        self.config.analysis, "semantic_similarity_threshold", 0.7
                    ),
                    time_window=getattr(
                        self.config.analysis, "repetition_time_window", 300
                    ),
                    max_segments_per_speaker=min(
                        len(segments_list),
                        getattr(
                            self.config.analysis, "max_segments_per_speaker", 300
                        ),
                    ),
                    filter_segments_fn=self.quality_scorer.filter_segments,
                    log_tag="SEMANTIC",
                )
                results["speaker_repetitions"][speaker] = speaker_reps

            if self.comparison_state.comparison_count <= self.max_comparisons:
                cross_speaker_reps = detect_cross_speaker_repetitions_basic(
                    segments=segments,
                    similarity_fn=self.calculate_semantic_similarity,
                    comparison_state=self.comparison_state,
                    similarity_threshold=getattr(
                        self.config.analysis, "cross_speaker_similarity_threshold", 0.6
                    ),
                    time_window=getattr(
                        self.config.analysis, "cross_speaker_time_window", 600
                    ),
                    max_segments_for_cross_speaker=getattr(
                        self.config.analysis, "max_segments_for_cross_speaker", 500
                    ),
                    log_tag="SEMANTIC",
                )
                results["cross_speaker_repetitions"] = cross_speaker_reps
            else:
                log_warning(
                    "SEMANTIC",
                    "Skipping cross-speaker analysis due to comparison limit",
                )

            if results["speaker_repetitions"] or results["cross_speaker_repetitions"]:
                def embedding_fn(text: str):
                    return get_text_embedding(
                        text,
                        self.model_manager.model,
                        self.model_manager.tokenizer,
                        self.model_manager.device,
                        self.model_manager.torch,
                        self.embedding_cache,
                        "SEMANTIC",
                    )

                clusters = cluster_repetitions_basic(
                    results["speaker_repetitions"],
                    results["cross_speaker_repetitions"],
                    embedding_fn,
                    "SEMANTIC",
                )
                results["repetition_clusters"] = clusters

            results["summary"] = generate_repetition_summary_basic(results)
            results["performance_metrics"]["comparisons_made"] = (
                self.comparison_state.comparison_count
            )
            return results
        except Exception as exc:
            log_error("SEMANTIC", f"Semantic analysis failed: {exc}")
            return {
                "repetitions": [],
                "speaker_repetitions": {},
                "cross_speaker_repetitions": [],
                "repetition_clusters": [],
                "summary": {"error": str(exc)},
                "performance_metrics": {
                    "segments_processed": len(segments),
                    "comparisons_made": self.comparison_state.comparison_count,
                    "timeout_reached": False,
                    "max_comparisons_exceeded": False,
                    "error": str(exc),
                },
            }

    def create_visualizations(
        self, results: dict[str, Any], output_service: Any, base_name: str
    ) -> list[str]:
        return create_visualizations_basic(results, output_service, base_name, "SEMANTIC")


class AdvancedSemanticSimilarityAnalyzer:
    """Advanced semantic similarity analyzer with analysis integration."""

    def __init__(self, config: Any | None = None):
        try:
            self.config = config or get_config()
            self.max_segments = getattr(
                self.config.analysis, "max_segments_for_semantic", 1000
            )
            self.max_comparisons = getattr(
                self.config.analysis, "max_semantic_comparisons", 50000
            )
            self.timeout_seconds = getattr(
                self.config.analysis, "semantic_timeout_seconds", 300
            )
            self.batch_size = getattr(self.config.analysis, "semantic_batch_size", 32)
            self.method = getattr(self.config.analysis, "semantic_method", "advanced")

            model_name = getattr(
                self.config.analysis,
                "semantic_model_name",
                "sentence-transformers/all-MiniLM-L6-v2",
            )
            self.model_manager = SemanticModelManager(
                config=self.config,
                model_name=model_name,
                log_tag="SEMANTIC_ADVANCED",
            )
            self.model_manager.initialize()

            self.embedding_cache = EmbeddingCache()
            self.similarity_calculator = SemanticSimilarityCalculator(
                self.model_manager, self.embedding_cache, "SEMANTIC_ADVANCED"
            )
            self.quality_scorer = AdvancedQualityScorer(self.config, "SEMANTIC_ADVANCED")

            self.comparison_state = ComparisonState(0, self.max_comparisons)
            self._limit_exceeded_warning_logged = False

            log_info("SEMANTIC_ADVANCED", f"Initialized with method: {self.method}")
        except Exception as exc:
            log_error(
                "SEMANTIC_ADVANCED",
                f"Failed to initialize analyzer: {exc}",
                exception=exc,
            )
            raise

    def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        self.comparison_state.comparison_count += 1
        if self.comparison_state.comparison_count > self.max_comparisons:
            if not self._limit_exceeded_warning_logged:
                log_warning(
                    "SEMANTIC_ADVANCED",
                    f"Exceeded maximum comparisons ({self.max_comparisons}), using TF-IDF fallback for remaining comparisons",
                )
                self._limit_exceeded_warning_logged = True
            return self.similarity_calculator.tfidf_similarity(text1, text2)
        return self.similarity_calculator.calculate(text1, text2)

    def detect_repetitions(
        self,
        segments: list[dict[str, Any]],
        speaker_map: dict[str, str] | None = None,
        transcript_path: str | None = None,
    ) -> dict[str, Any]:
        start_time = time.time()
        analysis_results: dict[str, Any] = {}
        if transcript_path and self.method == "advanced":
            analysis_results = load_analysis_results(transcript_path, "SEMANTIC_ADVANCED")

        try:
            if self.method == "advanced" and analysis_results:
                filtered_segments = self.quality_scorer.filter_segments(
                    segments, self.max_segments, analysis_results
                )
            else:
                filtered_segments = segments[: self.max_segments]

            speaker_repetitions = {}
            speaker_segments_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for seg in filtered_segments:
                speaker_info = extract_speaker_info(seg)
                if speaker_info is None:
                    continue
                speaker = get_speaker_display_name(
                    speaker_info.grouping_key, [seg], filtered_segments
                )
                if not speaker or not is_named_speaker(speaker):
                    continue
                speaker_segments_map[speaker].append(seg)

            for speaker, speaker_segments in speaker_segments_map.items():
                if len(speaker_segments) > 1:
                    speaker_repetitions[speaker] = detect_speaker_repetitions_advanced(
                        speaker,
                        speaker_segments,
                        self.calculate_semantic_similarity,
                        self.comparison_state,
                        "SEMANTIC_ADVANCED",
                    )

            cross_speaker_repetitions = detect_cross_speaker_repetitions_advanced(
                filtered_segments,
                self.calculate_semantic_similarity,
                self.comparison_state,
                "SEMANTIC_ADVANCED",
            )

            clusters = cluster_repetitions_advanced(
                speaker_repetitions, cross_speaker_repetitions, "SEMANTIC_ADVANCED"
            )

            summary = generate_repetition_summary_advanced(
                {
                    "speaker_repetitions": speaker_repetitions,
                    "cross_speaker_repetitions": cross_speaker_repetitions,
                    "clusters": clusters,
                },
                self.method,
                "SEMANTIC_ADVANCED",
            )

            duration = time.time() - start_time
            performance_metrics = {
                "segments_processed": len(filtered_segments),
                "comparisons_made": self.comparison_state.comparison_count,
                "processing_time_seconds": duration,
                "timeout_reached": False,
                "max_comparisons_exceeded": self.comparison_state.comparison_count
                >= self.max_comparisons,
                "method_used": self.method,
                "analysis_modules_integrated": len(analysis_results),
            }

            results = {
                "speaker_repetitions": speaker_repetitions,
                "cross_speaker_repetitions": cross_speaker_repetitions,
                "clusters": clusters,
                "summary": summary,
                "performance_metrics": performance_metrics,
                "analysis_integration": {
                    "method": self.method,
                    "modules_available": list(analysis_results.keys()),
                    "integration_successful": len(analysis_results) > 0,
                },
            }

            log_info(
                "SEMANTIC_ADVANCED",
                f"Analysis completed in {duration:.2f}s with {self.comparison_state.comparison_count} comparisons",
            )
            return results
        except Exception as exc:
            log_analysis_error("SEMANTIC_ADVANCED", transcript_path or "unknown", exc)
            return {
                "error": str(exc),
                "performance_metrics": {
                    "error_occurred": True,
                    "processing_time_seconds": time.time() - start_time,
                },
            }

    def create_visualizations(
        self, results: dict[str, Any], output_service: Any, base_name: str
    ) -> list[str]:
        return create_visualizations_advanced(
            results, output_service, base_name, "SEMANTIC_ADVANCED"
        )
