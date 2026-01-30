"""
Dialogue Act Classification Module for TranscriptX.
"""

import os
from collections import Counter, defaultdict
from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.acts.classification import classify_utterance
from transcriptx.core.analysis.acts.config import ClassificationMethod, get_act_config
from transcriptx.core.utils.path_utils import get_enriched_transcript_path
from transcriptx.io import save_transcript
from transcriptx.utils.text_utils import is_named_speaker


class ActsAnalysis(AnalysisModule):
    """
    Dialogue act classification analysis module.

    This module classifies utterances into dialogue act types using
    either ML-based classification, rules-based classification, or both.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the acts analysis module."""
        super().__init__(config)
        self.module_name = "acts"
        self.act_config = get_act_config()

    def analyze(
        self, segments: List[Dict[str, Any]], speaker_map: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Perform dialogue act classification on transcript segments (pure logic, no I/O).

        Uses database-driven speaker identification. speaker_map parameter is deprecated.

        Args:
            segments: List of transcript segments (should have speaker_db_id for proper identification)
            speaker_map: Deprecated - Speaker ID to name mapping (kept for backward compatibility only)

        Returns:
            Dictionary containing dialogue act classification results
        """
        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        tagged_segments = []
        act_counts_global = Counter()
        act_counts_per_speaker = defaultdict(Counter)
        act_confidence_scores = defaultdict(list)

        # For both methods, track separate results
        ml_segments = []
        rules_segments = []
        comparison_data = []

        # Build conversation context for better classification
        conversation_context = {
            "previous_utterances": [],
            "speaker_roles": {},
            "conversation_topic": "",
        }

        for i, seg in enumerate(segments):
            text = seg.get("text", "")

            # Extract speaker info using speaker_db_id when available
            speaker_info = extract_speaker_info(seg)
            if speaker_info is None:
                continue

            # Get display name for this speaker
            display_name = get_speaker_display_name(
                speaker_info.grouping_key, [seg], segments
            )

            # Create context for this utterance
            context = {
                "previous_utterances": conversation_context["previous_utterances"][-3:],
                "speaker_role": conversation_context["speaker_roles"].get(
                    display_name, ""
                ),
                "conversation_topic": conversation_context["conversation_topic"],
                "utterance_index": i,
                "total_utterances": len(segments),
            }

            # Classify with context
            classification_result = classify_utterance(text, context)

            # Extract act type and confidence from the result
            act = classification_result["act_type"]
            confidence = classification_result["confidence"]

            # Store results
            seg["dialogue_act"] = act
            seg["act_confidence"] = confidence
            seg["act_method"] = classification_result.get("method", "unknown")
            seg["act_probabilities"] = classification_result.get("probabilities", {})

            # Handle both methods results
            if self.act_config.method == ClassificationMethod.BOTH:
                ml_result = classification_result.get("ml_result", {})
                rules_result = classification_result.get("rules_result", {})

                # Create separate segments for each method
                ml_seg = seg.copy()
                ml_seg["dialogue_act"] = ml_result.get("act_type", "statement")
                ml_seg["act_confidence"] = ml_result.get("confidence", 0.5)
                ml_seg["act_method"] = "ml"
                ml_segments.append(ml_seg)

                rules_seg = seg.copy()
                rules_seg["dialogue_act"] = rules_result.get("act_type", "statement")
                rules_seg["act_confidence"] = rules_result.get("confidence", 0.5)
                rules_seg["act_method"] = "rules"
                rules_segments.append(rules_seg)

                # Store comparison data
                comparison_data.append(
                    {
                        "utterance_index": i,
                        "text": text,
                        "speaker": display_name,
                        "ml_act": ml_result.get("act_type", "statement"),
                        "ml_confidence": ml_result.get("confidence", 0.5),
                        "rules_act": rules_result.get("act_type", "statement"),
                        "rules_confidence": rules_result.get("confidence", 0.5),
                        "methods_agreed": classification_result.get(
                            "methods_agreed", False
                        ),
                        "confidence_difference": classification_result.get(
                            "confidence_difference", 0.0
                        ),
                    }
                )

            # Update conversation context
            conversation_context["previous_utterances"].append(text)
            if len(conversation_context["previous_utterances"]) > 10:
                conversation_context["previous_utterances"] = conversation_context[
                    "previous_utterances"
                ][-10:]

            # Count acts using display name (grouping by speaker_db_id happens via grouping_key)
            act_counts_global[act] += 1
            if is_named_speaker(display_name):
                act_counts_per_speaker[display_name][act] += 1
                act_confidence_scores[display_name].append(confidence)

            tagged_segments.append(seg)

        # Prepare summary data
        speaker_stats = {}
        for speaker, counts in act_counts_per_speaker.items():
            if is_named_speaker(speaker):
                avg_confidence = (
                    sum(act_confidence_scores[speaker])
                    / len(act_confidence_scores[speaker])
                    if act_confidence_scores[speaker]
                    else 0.0
                )
                speaker_stats[speaker] = {
                    "act_counts": dict(counts),
                    "avg_confidence": avg_confidence,
                    "total_acts": sum(counts.values()),
                }

        global_stats = {
            "act_counts": dict(act_counts_global),
            "total_acts": sum(act_counts_global.values()),
        }

        return {
            "tagged_segments": tagged_segments,
            "segments": tagged_segments,  # Alias for compatibility
            "acts": tagged_segments,  # Alias for compatibility
            "ml_segments": ml_segments,
            "rules_segments": rules_segments,
            "comparison_data": comparison_data,
            "act_counts_global": dict(act_counts_global),
            "act_counts_per_speaker": {
                k: dict(v) for k, v in act_counts_per_speaker.items()
            },
            "speaker_stats": speaker_stats,
            "global_stats": global_stats,
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
        tagged_segments = results["tagged_segments"]
        ml_segments = results["ml_segments"]
        rules_segments = results["rules_segments"]
        comparison_data = results["comparison_data"]
        act_counts_global = results["act_counts_global"]
        act_counts_per_speaker = results["act_counts_per_speaker"]
        base_name = output_service.base_name

        # Save enriched transcript
        enriched_path = get_enriched_transcript_path(
            output_service.transcript_path, "acts"
        )
        os.makedirs(os.path.dirname(enriched_path), exist_ok=True)
        save_transcript(tagged_segments, enriched_path)

        # Save global act counts
        output_service.save_data(act_counts_global, "acts_summary", format_type="json")

        # Save per-speaker data
        for speaker, counts in act_counts_per_speaker.items():
            if is_named_speaker(speaker):
                output_service.save_data(
                    counts,
                    f"acts_{speaker}",
                    format_type="json",
                    subdirectory="speakers",
                )

        # Save method-specific results if both methods were used
        if self.act_config.method == ClassificationMethod.BOTH:
            if ml_segments:
                output_service.save_data(ml_segments, "acts_ml", format_type="json")
            if rules_segments:
                output_service.save_data(
                    rules_segments, "acts_rules", format_type="json"
                )
            if comparison_data:
                output_service.save_data(
                    comparison_data, "acts_comparison", format_type="json"
                )

        # Generate and save charts (pie, bar, timeline per speaker and global)
        from transcriptx.core.analysis.acts.output import generate_acts_charts

        generate_acts_charts(
            output_service,
            tagged_segments,
            act_counts_global,
            act_counts_per_speaker,
            base_name,
        )

        # Save summary
        output_service.save_summary(
            results["global_stats"], results["speaker_stats"], analysis_metadata={}
        )
