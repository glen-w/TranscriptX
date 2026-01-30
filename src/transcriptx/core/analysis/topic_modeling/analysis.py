"""Topic modeling module."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.utils.lazy_imports import lazy_module

from transcriptx.core.analysis.base import AnalysisModule

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.nlp_utils import (
    has_meaningful_content,
    preprocess_for_topic_modeling,
)

# --- Robust JSON serialization for numpy types ---
from .utils import (
    prepare_text_data,
    analyze_discourse_topics,
)
from .lda import perform_enhanced_lda_analysis
from .nmf import perform_enhanced_nmf_analysis
from .visualization import (
    create_diagnostic_plots,
    create_discourse_analysis_charts,
    create_enhanced_global_heatmaps,
    create_speaker_charts,
    create_topic_evolution_timeline,
    create_speaker_topic_engagement_heatmap,
    create_expected_topic_proportions_bar,
    create_enhanced_html_report,
)


class TopicModelingAnalysis(AnalysisModule):
    """
    Topic modeling analysis module.

    This module provides advanced topic modeling using LDA and NMF with
    STM-inspired features.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the topic modeling analysis module."""
        super().__init__(config)
        self.module_name = "topic_modeling"
        self.logger = get_logger()

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform topic modeling analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping (deprecated, kept for backward compatibility)

        Returns:
            Dictionary containing topic modeling results
        """
        mpl = lazy_module("matplotlib", "plotting", "visualization")
        sns = lazy_module("seaborn", "plotting", "visualization")
        mpl.rcdefaults()
        sns.reset_defaults()
        sns.set_theme(style="whitegrid")

        # Prepare text data (speaker_map parameter removed, uses database-driven approach)
        texts, speaker_labels, time_labels = prepare_text_data(segments)

        if not texts:
            # Provide diagnostic information about why no valid text was found
            total_segments = len(segments)
            meaningful_count = sum(
                1
                for seg in segments
                if has_meaningful_content(
                    seg.get("text", "").strip(),
                    preprocessing_func=preprocess_for_topic_modeling,
                )
            )
            return {
                "error": "No valid text data found for topic modeling",
                "message": f"Topic modeling failed - insufficient data after preprocessing. Total segments: {total_segments}, segments with meaningful content: {meaningful_count}",
                "topics": [],
                "models": {},
                "diagnostics": {
                    "total_segments": total_segments,
                    "meaningful_segments_after_preprocessing": meaningful_count,
                    "reason": "All segments were filtered out during preprocessing (likely too short or contain only stopwords/tics after content word filtering)",
                },
            }

        # Check if we have enough segments for topic modeling (LDA/NMF require at least 3)
        if len(texts) < 3:
            return {
                "error": f"Need at least 3 text segments for LDA analysis, but only {len(texts)} segment(s) found after preprocessing",
                "topics": [],
                "models": {},
                "texts_count": len(texts),
            }

        # Perform enhanced topic modeling with optimal k selection
        lda_results = perform_enhanced_lda_analysis(texts, speaker_labels, time_labels)
        nmf_results = perform_enhanced_nmf_analysis(texts, speaker_labels, time_labels)

        # Remove non-serializable objects (model and vectorizer) before returning
        # These are scikit-learn objects that cannot be JSON serialized
        # Convert doc_topics numpy array to list for JSON serialization
        lda_results_clean = {}
        for k, v in lda_results.items():
            if k == "model" or k == "vectorizer":
                continue  # Skip non-serializable objects
            elif k == "doc_topics":
                # Convert numpy array to list for JSON serialization
                lda_results_clean[k] = v.tolist() if hasattr(v, "tolist") else v
            else:
                lda_results_clean[k] = v

        nmf_results_clean = {}
        for k, v in nmf_results.items():
            if k == "model" or k == "vectorizer":
                continue  # Skip non-serializable objects
            elif k == "doc_topics":
                # Convert numpy array to list for JSON serialization
                nmf_results_clean[k] = v.tolist() if hasattr(v, "tolist") else v
            else:
                nmf_results_clean[k] = v

        # Perform discourse analysis on LDA results
        discourse_analysis = analyze_discourse_topics(lda_results["doc_topic_data"])

        return {
            "lda_results": lda_results_clean,
            "nmf_results": nmf_results_clean,
            "discourse_analysis": discourse_analysis,
            "texts": texts,
            "speaker_labels": speaker_labels,
            "time_labels": time_labels,
        }

    def _save_results(
        self, results: Dict[str, Any], output_service: "OutputService"
    ) -> None:
        """
        Save results using OutputService (new interface).

        Args:
            results: Analysis results dictionary
            output_service: OutputService instance
        """
        base_name = output_service.base_name
        output_structure = output_service.get_output_structure()

        # Extract results
        lda_results = results.get("lda_results", {})
        nmf_results = results.get("nmf_results", {})
        discourse_analysis = results.get("discourse_analysis", {})
        speaker_labels = results.get("speaker_labels", [])

        # Check for errors
        if "error" in results:
            error_data = {
                "error": results["error"],
                "message": results.get(
                    "message", "Topic modeling failed - insufficient data"
                ),
            }
            # Include diagnostics if available
            if "diagnostics" in results:
                error_data["diagnostics"] = results["diagnostics"]
            # Include texts_count if available (for segments < 3 case)
            if "texts_count" in results:
                error_data["texts_count"] = results["texts_count"]
            output_service.save_data(
                error_data, "topic_modeling_error", format_type="json"
            )
            return

        # Save LDA topics
        if "topics" in lda_results:
            output_service.save_data(
                lda_results["topics"], "enhanced_lda_topics", format_type="json"
            )

        # Save NMF topics
        if "topics" in nmf_results:
            output_service.save_data(
                nmf_results["topics"], "enhanced_nmf_topics", format_type="json"
            )

        # Save document-topic assignments
        if "doc_topic_data" in lda_results:
            output_service.save_data(
                lda_results["doc_topic_data"], "lda_document_topics", format_type="json"
            )

        if "doc_topic_data" in nmf_results:
            output_service.save_data(
                nmf_results["doc_topic_data"], "nmf_document_topics", format_type="json"
            )

        # Save diagnostic metrics if available
        if "diagnostics" in lda_results:
            output_service.save_data(
                lda_results["diagnostics"], "lda_diagnostics", format_type="json"
            )

        if "diagnostics" in nmf_results:
            output_service.save_data(
                nmf_results["diagnostics"], "nmf_diagnostics", format_type="json"
            )

        # Save discourse analysis
        if discourse_analysis:
            output_service.save_data(
                discourse_analysis, "discourse_analysis", format_type="json"
            )

        # Generate visualizations using existing functions
        chart_paths = []

        # Enhanced global heatmaps
        try:
            create_enhanced_global_heatmaps(
                lda_results,
                nmf_results,
                base_name,
                output_structure,
                html_imgs=chart_paths,
                output_service=output_service,
            )
        except Exception as e:
            self.logger.warning(f"[TOPICS] Could not create global heatmaps: {e}")

        # Diagnostic plots
        try:
            if "diagnostics" in lda_results:
                create_diagnostic_plots(
                    lda_results["diagnostics"],
                    "lda",
                    base_name,
                    output_structure,
                    output_service=output_service,
                )

            if "diagnostics" in nmf_results:
                create_diagnostic_plots(
                    nmf_results["diagnostics"],
                    "nmf",
                    base_name,
                    output_structure,
                    output_service=output_service,
                )
        except Exception as e:
            self.logger.warning(f"[TOPICS] Could not create diagnostic plots: {e}")

        # Discourse analysis charts
        try:
            if discourse_analysis:
                create_discourse_analysis_charts(
                    discourse_analysis,
                    base_name,
                    output_structure,
                    output_service=output_service,
                )
        except Exception as e:
            self.logger.warning(
                f"[TOPICS] Could not create discourse analysis charts: {e}"
            )

        # Speaker charts (speaker_labels already contain display names from prepare_text_data)
        try:
            create_speaker_charts(
                lda_results,
                nmf_results,
                speaker_labels,
                base_name,
                output_structure,
                html_imgs=chart_paths,
                output_service=output_service,
            )
        except Exception as e:
            self.logger.warning(f"[TOPICS] Could not create speaker charts: {e}")

        # Additional visualizations
        try:
            if "doc_topic_data" in lda_results:
                create_topic_evolution_timeline(
                    lda_results["doc_topic_data"],
                    base_name,
                    output_structure,
                    lda_topics=lda_results.get("topics"),
                    output_service=output_service,
                )
        except Exception as e:
            self.logger.warning(
                f"[TOPICS] Could not create topic evolution timeline: {e}"
            )

        try:
            if "doc_topic_data" in lda_results:
                create_speaker_topic_engagement_heatmap(
                    lda_results["doc_topic_data"],
                    base_name,
                    output_structure,
                    lda_topics=lda_results.get("topics"),
                    output_service=output_service,
                )
        except Exception as e:
            self.logger.warning(
                f"[TOPICS] Could not create speaker-topic engagement heatmap: {e}"
            )

        try:
            if "doc_topic_data" in lda_results and "topics" in lda_results:
                create_expected_topic_proportions_bar(
                    lda_results["doc_topic_data"],
                    lda_results["topics"],
                    base_name,
                    output_structure,
                    output_service=output_service,
                )
        except Exception as e:
            self.logger.warning(
                f"[TOPICS] Could not create expected topic proportions bar chart: {e}"
            )

        # Create enhanced HTML report
        try:
            html_path = (
                output_structure.module_dir
                / f"{base_name}_enhanced_topic_modeling_report.html"
            )
            create_enhanced_html_report(
                html_path, chart_paths, lda_results, nmf_results, discourse_analysis
            )
        except Exception as e:
            self.logger.warning(f"[TOPICS] Could not create HTML report: {e}")
