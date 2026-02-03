"""
Entity Sentiment Framing Analysis Module for TranscriptX.

This module analyzes the sentiment framing of named entities in transcripts.
It computes sentiment scores for each recognized entity (PERSON, ORG, GPE, LOC)
and provides comprehensive analysis of how entities are discussed.
"""

from collections import Counter, defaultdict
from typing import Any, Dict, List

import numpy as np

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.analysis.ner import extract_named_entities
from transcriptx.core.analysis.sentiment import score_sentiment
from transcriptx.core.utils.nlp_utils import preprocess_for_sentiment
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.core.utils.lazy_imports import lazy_pyplot
from transcriptx.core.utils.viz_ids import (
    VIZ_ENTITY_SENTIMENT_HEATMAP,
    VIZ_ENTITY_SENTIMENT_TYPE_ANALYSIS,
    VIZ_ENTITY_SENTIMENT_MENTIONS_SPEAKER,
)
from transcriptx.core.viz.specs import BarCategoricalSpec, HeatmapMatrixSpec

plt = lazy_pyplot()


def normalize_entity_name(entity_name: str) -> str:
    """
    Normalize entity names for consistent matching.

    Args:
        entity_name: Raw entity name

    Returns:
        Normalized entity name
    """
    # Common normalizations
    normalizations = {
        "u.s.": "United States",
        "usa": "United States",
        "us": "United States",
        "uk": "United Kingdom",
        "united kingdom": "United Kingdom",
        "united states": "United States",
        "new york city": "New York",
        "nyc": "New York",
        "los angeles": "LA",
        "la": "Los Angeles",
        "san francisco": "San Francisco",
        "sf": "San Francisco",
    }

    normalized = entity_name.lower().strip()
    return normalizations.get(normalized, entity_name.title())


class EntitySentimentAnalysis(AnalysisModule):
    """
    Entity sentiment analysis module.

    This module analyzes sentiment framing for named entities in transcripts,
    requiring NER and sentiment data from other modules.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the entity sentiment analysis module."""
        super().__init__(config)
        self.module_name = "entity_sentiment"

    def analyze(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] = None,
        ner_data: Dict[str, Any] = None,
        sentiment_data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Perform entity sentiment analysis on transcript segments (pure logic, no I/O).

        Args:
            segments: List of transcript segments
            speaker_map: Speaker ID to name mapping
            ner_data: Optional pre-computed NER data (from PipelineContext)
            sentiment_data: Optional pre-computed sentiment data (from PipelineContext)

        Returns:
            Dictionary containing entity sentiment analysis results
        """
        # Initialize data structures
        entity_mentions = defaultdict(list)
        entity_speaker_mentions = defaultdict(lambda: defaultdict(list))

        # Build entity map from NER data if available
        entity_map = {}
        if ner_data and isinstance(ner_data, dict):
            # Extract entity information from NER results
            # This is a simplified approach - full implementation would parse NER results
            pass

        # Build sentiment map from sentiment data if available
        sentiment_map = {}
        if sentiment_data and isinstance(sentiment_data, dict):
            # Extract sentiment scores from sentiment results
            segments_with_sentiment = sentiment_data.get("segments_with_sentiment", [])
            for seg in segments_with_sentiment:
                seg_idx = (
                    segments_with_sentiment.index(seg)
                    if seg in segments_with_sentiment
                    else None
                )
                if seg_idx is not None and seg_idx < len(segments):
                    sentiment_map[seg_idx] = seg.get("sentiment", {})

        from transcriptx.core.utils.speaker_extraction import (
            extract_speaker_info,
            get_speaker_display_name,
        )

        # Process each segment
        for i, segment in enumerate(segments):
            text = segment.get("text", "")
            speaker_info = extract_speaker_info(segment)
            if speaker_info is None:
                continue
            speaker = get_speaker_display_name(
                speaker_info.grouping_key, [segment], segments
            )

            # Skip segments from unnamed speakers
            if not speaker or not is_named_speaker(speaker):
                continue

            # Extract entities from this segment
            # Use cached NER data if available, otherwise compute
            if i in entity_map:
                entities = entity_map[i]
            else:
                entities = extract_named_entities(text)

            # Calculate sentiment for this segment
            # Use cached sentiment data if available, otherwise compute
            if i in sentiment_map:
                sentiment_score = sentiment_map[i]
            else:
                preprocessed_text = preprocess_for_sentiment(text)
                if preprocessed_text:
                    sentiment_score = score_sentiment(preprocessed_text)
                else:
                    sentiment_score = score_sentiment(text)

            # Group entities by normalized name
            for entity_text, entity_type in entities:
                # Only analyze specific entity types
                if entity_type not in ["PERSON", "ORG", "GPE", "LOC"]:
                    continue

                normalized_name = normalize_entity_name(entity_text)

                # Store mention with metadata
                mention_data = {
                    "segment_index": i,
                    "text": text,
                    "speaker": speaker,
                    "entity_type": entity_type,
                    "sentiment_compound": sentiment_score.get("compound", 0),
                    "sentiment_pos": sentiment_score.get("pos", 0),
                    "sentiment_neu": sentiment_score.get("neu", 0),
                    "sentiment_neg": sentiment_score.get("neg", 0),
                    "timestamp": segment.get("start", 0),
                }

                entity_mentions[normalized_name].append(mention_data)
                entity_speaker_mentions[normalized_name][speaker].append(mention_data)

        # Calculate statistics for each entity
        entity_stats = {}
        for entity_name, mentions in entity_mentions.items():
            if len(mentions) < 2:  # Filter entities mentioned less than 2 times
                continue

            # Extract sentiment scores
            compound_scores = [m["sentiment_compound"] for m in mentions]

            # Calculate statistics
            avg_compound = np.mean(compound_scores)
            std_compound = np.std(compound_scores)

            # Count sentiment polarities
            pos_count = sum(1 for score in compound_scores if score > 0.05)
            neg_count = sum(1 for score in compound_scores if score < -0.05)
            neu_count = len(compound_scores) - pos_count - neg_count

            # Get example segments (up to 3)
            example_segments = [
                m["text"][:200] + "..." if len(m["text"]) > 200 else m["text"]
                for m in mentions[:3]
            ]

            entity_stats[entity_name] = {
                "mention_count": len(mentions),
                "avg_sentiment": avg_compound,
                "std_sentiment": std_compound,
                "pos_count": pos_count,
                "neu_count": neu_count,
                "neg_count": neg_count,
                "entity_type": mentions[0]["entity_type"],
                "example_segments": example_segments,
                "speaker_breakdown": {
                    speaker: len(speaker_mentions)
                    for speaker, speaker_mentions in entity_speaker_mentions[
                        entity_name
                    ].items()
                },
            }

        speaker_entity_sentiment = {}
        for entity_name, speaker_mentions in entity_speaker_mentions.items():
            for speaker, mentions in speaker_mentions.items():
                if speaker not in speaker_entity_sentiment:
                    speaker_entity_sentiment[speaker] = {}
                speaker_entity_sentiment[speaker][entity_name] = len(mentions)

        result = {
            "entity_stats": entity_stats,
            "total_entities": len(entity_stats),
            "total_mentions": sum(
                stats["mention_count"] for stats in entity_stats.values()
            ),
        }
        # Backward-compatible keys for tests/legacy consumers
        result["entity_sentiment"] = entity_stats
        result["entities"] = list(entity_stats.keys())
        result["speaker_entity_sentiment"] = speaker_entity_sentiment
        result["speaker_mentions"] = speaker_entity_sentiment
        result["summary"] = {
            "total_entities": result["total_entities"],
            "total_mentions": result["total_mentions"],
        }
        return result

    def run_from_context(self, context: "PipelineContext") -> Dict[str, Any]:
        """
        Run entity sentiment analysis using PipelineContext (can access cached results).

        Args:
            context: PipelineContext containing transcript data and cached results

        Returns:
            Dictionary containing analysis results and metadata
        """
        try:
            from transcriptx.core.utils.logger import (
                log_analysis_start,
                log_analysis_complete,
                log_analysis_error,
            )

            log_analysis_start(self.module_name, context.transcript_path)

            # Extract data from context
            segments = context.get_segments()
            speaker_map = context.get_speaker_map()

            # Try to get cached results from other modules
            ner_result = context.get_analysis_result("ner")
            sentiment_result = context.get_analysis_result("sentiment")

            # Perform analysis with cached data if available
            results = self.analyze(
                segments,
                speaker_map,
                ner_data=ner_result,
                sentiment_data=sentiment_result,
            )

            # Create output service and save results
            from transcriptx.core.output.output_service import create_output_service

            output_service = create_output_service(
                context.transcript_path,
                self.module_name,
                output_dir=context.get_transcript_dir(),
                run_id=context.get_run_id(),
                runtime_flags=context.get_runtime_flags(),
            )
            self.save_results(results, output_service=output_service)

            # Store result in context
            context.store_analysis_result(self.module_name, results)

            log_analysis_complete(self.module_name, context.transcript_path)

            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "success",
                "results": results,
                "output_directory": str(
                    output_service.get_output_structure().module_dir
                ),
            }

        except Exception as e:
            from transcriptx.core.utils.logger import log_analysis_error

            log_analysis_error(self.module_name, context.transcript_path, str(e))
            return {
                "module": self.module_name,
                "transcript_path": context.transcript_path,
                "status": "error",
                "error": str(e),
                "results": {},
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
        entity_stats = results["entity_stats"]
        base_name = output_service.base_name
        output_structure = output_service.get_output_structure()

        # Prepare CSV data
        csv_rows = []
        for entity_name, stats in entity_stats.items():
            row = {
                "entity": entity_name,
                "entity_type": stats["entity_type"],
                "mention_count": stats["mention_count"],
                "avg_sentiment": stats["avg_sentiment"],
                "std_sentiment": stats["std_sentiment"],
                "pos_count": stats["pos_count"],
                "neu_count": stats["neu_count"],
                "neg_count": stats["neg_count"],
            }
            csv_rows.append(row)

        # Save global data
        output_service.save_data(csv_rows, "entity_sentiment", format_type="csv")
        output_service.save_data(results, "entity_sentiment", format_type="json")

        # Create per-speaker breakdown
        speaker_entity_data = defaultdict(list)
        for entity_name, stats in entity_stats.items():
            for speaker, count in stats["speaker_breakdown"].items():
                speaker_entity_data[speaker].append(
                    {
                        "entity": entity_name,
                        "entity_type": stats["entity_type"],
                        "mention_count": count,
                        "avg_sentiment": stats["avg_sentiment"],
                        "std_sentiment": stats["std_sentiment"],
                    }
                )

        # Save per-speaker data
        for speaker, data in speaker_entity_data.items():
            output_service.save_data(
                data,
                "entity_sentiment",
                format_type="csv",
                subdirectory="speakers",
                speaker=speaker,
            )
            output_service.save_data(
                {"entities": data},
                "entity_sentiment",
                format_type="json",
                subdirectory="speakers",
                speaker=speaker,
            )

        # Generate visualizations using existing functions
        if entity_stats:
            self._create_sentiment_heatmap(
                results, output_structure, base_name, output_service
            )
            self._create_entity_type_analysis(
                results, output_structure, base_name, output_service
            )
            self._create_speaker_entity_analysis(
                results, output_structure, base_name, output_service
            )

        # Create comprehensive summary
        self._create_analysis_summary(
            results, output_structure, base_name, output_service
        )

    def _create_sentiment_heatmap(
        self,
        analysis_results: Dict[str, Any],
        output_structure,
        base_name: str,
        output_service: "OutputService",
    ) -> None:
        """Create sentiment heatmap chart."""
        entity_stats = analysis_results["entity_stats"]
        if not entity_stats:
            return

        top_entities = sorted(
            entity_stats.items(), key=lambda x: x[1]["mention_count"], reverse=True
        )[:20]

        if not top_entities:
            return

        entity_names = [entity for entity, _ in top_entities]
        mention_counts = [stats["mention_count"] for _, stats in top_entities]
        avg_sentiments = [stats["avg_sentiment"] for _, stats in top_entities]

        heatmap_data = np.array(
            [
                [count, sentiment]
                for count, sentiment in zip(
                    mention_counts, avg_sentiments, strict=False
                )
            ]
        )
        spec = HeatmapMatrixSpec(
            viz_id=VIZ_ENTITY_SENTIMENT_HEATMAP,
            module=self.module_name,
            name="sentiment_heatmap",
            scope="global",
            chart_intent="heatmap_matrix",
            title=f"Entity Sentiment Heatmap - Top 20 Entities by Frequency\n{base_name}",
            x_label="Entity",
            y_label="Metric",
            z=heatmap_data.T.tolist(),
            x_labels=entity_names,
            y_labels=["Mention Count", "Avg Sentiment"],
        )
        output_service.save_chart(spec, chart_type="heatmap")

    def _create_entity_type_analysis(
        self,
        analysis_results: Dict[str, Any],
        output_structure,
        base_name: str,
        output_service: "OutputService",
    ) -> None:
        """Create entity type analysis charts."""
        entity_stats = analysis_results["entity_stats"]
        if not entity_stats:
            return

        type_stats = defaultdict(list)
        for entity_name, stats in entity_stats.items():
            type_stats[stats["entity_type"]].append(stats)

        categories = []
        values = []
        for entity_type, stats_list in type_stats.items():
            if not stats_list:
                continue
            avg = float(np.mean([s["avg_sentiment"] for s in stats_list]))
            categories.append(entity_type)
            values.append(avg)

        if not categories:
            return

        spec = BarCategoricalSpec(
            viz_id=VIZ_ENTITY_SENTIMENT_TYPE_ANALYSIS,
            module=self.module_name,
            name="entity_type_analysis",
            scope="global",
            chart_intent="bar_categorical",
            title=f"Entity Sentiment Analysis by Type - {base_name}",
            x_label="Entity Type",
            y_label="Average Sentiment Score",
            categories=categories,
            values=values,
        )
        output_service.save_chart(spec, chart_type="bar")

    def _create_speaker_entity_analysis(
        self,
        analysis_results: Dict[str, Any],
        output_structure,
        base_name: str,
        output_service: "OutputService",
    ) -> None:
        """Create speaker entity analysis charts."""
        entity_stats = analysis_results["entity_stats"]
        if not entity_stats:
            return

        speaker_entity_counts = defaultdict(Counter)
        for entity_name, stats in entity_stats.items():
            for speaker, count in stats["speaker_breakdown"].items():
                if not is_named_speaker(speaker):
                    continue
                speaker_entity_counts[speaker][entity_name] = count

        for speaker, entity_counts in speaker_entity_counts.items():
            if not entity_counts:
                continue

            top_entities = entity_counts.most_common(10)
            if not top_entities:
                continue

            entity_names, counts = zip(*top_entities, strict=False)
            sentiments = [
                (
                    entity_stats[entity_name]["avg_sentiment"]
                    if entity_name in entity_stats
                    else 0
                )
                for entity_name in entity_names
            ]

            plt.figure(figsize=(10, 6))
            bars = plt.bar(
                range(len(entity_names)),
                counts,
                color=[
                    "red" if s < -0.1 else "blue" if s > 0.1 else "gray"
                    for s in sentiments
                ],
            )
            spec = BarCategoricalSpec(
                viz_id=VIZ_ENTITY_SENTIMENT_MENTIONS_SPEAKER,
                module=self.module_name,
                name="entity_mentions",
                scope="speaker",
                speaker=speaker,
                chart_intent="bar_categorical",
                title=f"{speaker}'s Entity Mentions - {base_name}",
                x_label="Entity",
                y_label="Mention Count",
                categories=list(entity_names),
                values=list(counts),
            )
            output_service.save_chart(spec, chart_type="bar")

    def _create_analysis_summary(
        self,
        analysis_results: Dict[str, Any],
        output_structure,
        base_name: str,
        output_service: "OutputService",
    ) -> None:
        """Create analysis summary."""
        entity_stats = analysis_results["entity_stats"]

        summary = {
            "total_entities": len(entity_stats),
            "total_mentions": sum(
                stats["mention_count"] for stats in entity_stats.values()
            ),
            "entity_types": dict(
                Counter(stats["entity_type"] for stats in entity_stats.values())
            ),
            "most_mentioned_entities": sorted(
                entity_stats.items(), key=lambda x: x[1]["mention_count"], reverse=True
            )[:10],
            "most_positive_entities": sorted(
                entity_stats.items(), key=lambda x: x[1]["avg_sentiment"], reverse=True
            )[:10],
            "most_negative_entities": sorted(
                entity_stats.items(), key=lambda x: x[1]["avg_sentiment"]
            )[:10],
        }

        output_service.save_data(summary, "summary", format_type="json")

        # Create text summary
        summary_text = f"""Entity Sentiment Analysis Summary: {base_name}
{'=' * 60}

Total Entities Analyzed: {summary['total_entities']}
Total Entity Mentions: {summary['total_mentions']}

Entity Type Distribution:
"""
        for entity_type, count in summary["entity_types"].items():
            summary_text += f"  • {entity_type}: {count}\n"

        summary_text += "\nMost Mentioned Entities:\n"
        for entity_name, stats in summary["most_mentioned_entities"]:
            summary_text += f"  • {entity_name}: {stats['mention_count']} mentions (avg sentiment: {stats['avg_sentiment']:.3f})\n"

        summary_text += "\nMost Positively Framed Entities:\n"
        for entity_name, stats in summary["most_positive_entities"]:
            summary_text += f"  • {entity_name}: {stats['avg_sentiment']:.3f} (mentioned {stats['mention_count']} times)\n"

        summary_text += "\nMost Negatively Framed Entities:\n"
        for entity_name, stats in summary["most_negative_entities"]:
            summary_text += f"  • {entity_name}: {stats['avg_sentiment']:.3f} (mentioned {stats['mention_count']} times)\n"

        output_service.save_data(summary_text, "summary", format_type="txt")

        # Save summary using OutputService
        speaker_stats = {}
        global_stats = {
            "total_entities": summary["total_entities"],
            "total_mentions": summary["total_mentions"],
        }
        output_service.save_summary(global_stats, speaker_stats, analysis_metadata={})
