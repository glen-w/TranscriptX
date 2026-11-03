"""
Registry for group aggregation modules.

Implementation of inline row/blob aggregators lives in ``aggregators.py``.
This module owns ``AggregationEntry`` and ``build_registry()`` only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from transcriptx.core.analysis.aggregation.aggregators import (
    _aggregate_acts,
    _aggregate_affect_tension,
    _aggregate_contagion,
    _aggregate_conversation_loops,
    _aggregate_echoes,
    _aggregate_highlights,
    _aggregate_insight_eligibility,
    _aggregate_lexical_diversity,
    _aggregate_moments,
    _aggregate_momentum,
    _aggregate_pauses,
    _aggregate_prosody,
    _aggregate_qa_analysis,
    _aggregate_simplified_transcript,
    _aggregate_summary_blob,
    _aggregate_temporal_dynamics,
    _aggregate_tics,
    _aggregate_transcript_output_blob,
    _aggregate_understandability,
    _aggregate_voice_contours,
    _aggregate_wordclouds,
    _artifact_relpath,
    _extract_highlight_items,
    _resolve_prosody_summary_path,
)
from transcriptx.core.analysis.aggregation.common import (
    warning_payload_shape as _warning_payload_shape,
)
from transcriptx.core.analysis.aggregation.warnings import build_warning
from transcriptx.core.analysis.epistemic_markers.aggregation import (
    aggregate_epistemic_markers,
)
from transcriptx.core.analysis.keyphrases.aggregation import aggregate_keyphrases
from transcriptx.core.analysis.names.aggregation import aggregate_names
from transcriptx.core.analysis.politeness.aggregation import aggregate_politeness
from transcriptx.core.analysis.topic_shift.aggregation import aggregate_topic_shift
from transcriptx.core.analysis.speaker_map_diagnostics.aggregation import (
    aggregate_speaker_map_diagnostics,
)
from transcriptx.core.analysis.transcript_quality.aggregation import (
    aggregate_transcript_quality,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap

AggregationContext = Dict[str, Any]
AggregationFn = Callable[
    [
        List[PerTranscriptResult],
        CanonicalSpeakerMap,
        TranscriptSet,
        Optional[AggregationContext],
    ],
    Dict[str, Any] | None,
]


@dataclass(frozen=True)
class AggregationEntry:
    agg_id: str
    selector: Callable[[List[str]], bool]
    deps: List[str]
    aggregate_fn: AggregationFn
    output_type: str = "rows"  # "rows" or "blob"


# Helper names tests still import from this catalog module.
__all__ = [
    "AggregationContext",
    "AggregationEntry",
    "AggregationFn",
    "build_registry",
    "_artifact_relpath",
    "_extract_highlight_items",
    "_resolve_prosody_summary_path",
    "_warning_payload_shape",
]


def build_registry() -> List[AggregationEntry]:
    from transcriptx.core.analysis.stats.aggregation import aggregate_stats_group
    from transcriptx.core.analysis.aggregation.sentiment import (
        aggregate_sentiment_group,
    )
    from transcriptx.core.analysis.aggregation.ner import aggregate_ner_group
    from transcriptx.core.analysis.aggregation.entity_sentiment import (
        aggregate_entity_sentiment_group,
    )
    from transcriptx.core.analysis.aggregation.topics import aggregate_topics_group
    from transcriptx.core.analysis.aggregation.bertopic import aggregate_bertopic_group
    from transcriptx.core.analysis.aggregation.emotion import aggregate_emotion_group
    from transcriptx.core.analysis.aggregation.contextual_emotion import (
        aggregate_contextual_emotion_group,
        aggregate_fine_grained_emotion_group,
    )
    from transcriptx.core.analysis.aggregation.interactions import (
        aggregate_interactions_group,
    )
    from transcriptx.core.analysis.aggregation.llm import (
        aggregate_llm_action_items_group,
        aggregate_llm_speaker_summary_group,
        aggregate_llm_summary_blob,
        aggregate_narrative_summary_blob,
    )
    from transcriptx.core.analysis.aggregation.insights import aggregate_insights_group
    from transcriptx.core.analysis.aggregation.semantic_similarity import (
        aggregate_semantic_similarity_group,
    )
    from transcriptx.core.analysis.aggregation.voice import (
        aggregate_voice_fingerprint_group,
        aggregate_voice_mismatch_group,
        aggregate_voice_tension_group,
    )

    def _disabled_llm_custom_qa_group_agg(
        results: List[PerTranscriptResult],
        context: AggregationContext,
        canonical_map: Optional[CanonicalSpeakerMap] = None,
    ) -> Dict[str, Any]:
        """Registry-level disable until v2 aggregation is activation-enabled."""
        return {
            "schema_id": "transcriptx.llm_custom_qa.group.disabled",
            "disabled": True,
            "reason": "llm_custom_qa_group_aggregation_disabled_pending_structured",
            "content_rows": [],
            "content_rows_name": "qa_answer_rows",
            "warnings": [
                build_warning(
                    code="llm_custom_qa_agg_disabled",
                    message=(
                        "Custom QA group aggregation is disabled until v2 loader is enabled"
                    ),
                    aggregation_key="llm_custom_qa",
                )
            ],
        }

    def any_of(ids: List[str]) -> Callable[[List[str]], bool]:
        return lambda selected: any(module_id in selected for module_id in ids)

    registry: List[AggregationEntry] = [
        AggregationEntry(
            agg_id="stats",
            selector=any_of(["stats"]),
            deps=[],
            aggregate_fn=aggregate_stats_group,
        ),
        AggregationEntry(
            agg_id="sentiment",
            selector=any_of(["sentiment"]),
            deps=[],
            aggregate_fn=aggregate_sentiment_group,
        ),
        AggregationEntry(
            agg_id="ner",
            selector=any_of(["ner"]),
            deps=[],
            aggregate_fn=aggregate_ner_group,
        ),
        AggregationEntry(
            agg_id="names",
            selector=any_of(["names"]),
            deps=["ner"],
            aggregate_fn=aggregate_names,
        ),
        AggregationEntry(
            agg_id="entity_sentiment",
            selector=any_of(["entity_sentiment"]),
            deps=["ner"],
            aggregate_fn=aggregate_entity_sentiment_group,
        ),
        AggregationEntry(
            agg_id="topic_modeling",
            selector=any_of(["topic_modeling"]),
            deps=[],
            aggregate_fn=aggregate_topics_group,
        ),
        AggregationEntry(
            agg_id="bertopic",
            selector=any_of(["bertopic"]),
            deps=[],
            aggregate_fn=aggregate_bertopic_group,
        ),
        AggregationEntry(
            agg_id="emotion",
            selector=any_of(["emotion"]),
            deps=[],
            aggregate_fn=aggregate_emotion_group,
        ),
        AggregationEntry(
            agg_id="contextual_emotion",
            selector=any_of(["contextual_emotion"]),
            deps=[],
            aggregate_fn=aggregate_contextual_emotion_group,
        ),
        AggregationEntry(
            agg_id="fine_grained_emotion",
            selector=any_of(["fine_grained_emotion"]),
            deps=[],
            aggregate_fn=aggregate_fine_grained_emotion_group,
        ),
        AggregationEntry(
            agg_id="interactions",
            selector=any_of(["interactions"]),
            deps=[],
            aggregate_fn=aggregate_interactions_group,
        ),
        AggregationEntry(
            agg_id="wordclouds",
            selector=any_of(["wordclouds"]),
            deps=[],
            aggregate_fn=_aggregate_wordclouds,
        ),
        AggregationEntry(
            agg_id="acts",
            selector=any_of(["acts"]),
            deps=[],
            aggregate_fn=_aggregate_acts,
        ),
        AggregationEntry(
            agg_id="tics",
            selector=any_of(["tics"]),
            deps=[],
            aggregate_fn=_aggregate_tics,
        ),
        AggregationEntry(
            agg_id="transcript_quality",
            selector=any_of(["transcript_quality"]),
            deps=[],
            aggregate_fn=aggregate_transcript_quality,
        ),
        AggregationEntry(
            agg_id="speaker_map_diagnostics",
            selector=any_of(["speaker_map_diagnostics"]),
            deps=[],
            aggregate_fn=aggregate_speaker_map_diagnostics,
        ),
        AggregationEntry(
            agg_id="epistemic_markers",
            selector=any_of(["epistemic_markers"]),
            deps=[],
            aggregate_fn=aggregate_epistemic_markers,
        ),
        AggregationEntry(
            agg_id="keyphrases",
            selector=any_of(["keyphrases"]),
            deps=[],
            aggregate_fn=aggregate_keyphrases,
        ),
        AggregationEntry(
            agg_id="politeness",
            selector=any_of(["politeness"]),
            deps=[],
            aggregate_fn=aggregate_politeness,
        ),
        AggregationEntry(
            agg_id="topic_shift",
            selector=any_of(["topic_shift"]),
            deps=[],
            aggregate_fn=aggregate_topic_shift,
        ),
        AggregationEntry(
            agg_id="insight_eligibility",
            selector=any_of(["insight_eligibility"]),
            deps=["tics"],
            aggregate_fn=_aggregate_insight_eligibility,
        ),
        AggregationEntry(
            agg_id="understandability",
            selector=any_of(["understandability"]),
            deps=[],
            aggregate_fn=_aggregate_understandability,
        ),
        AggregationEntry(
            agg_id="lexical_diversity",
            selector=any_of(["lexical_diversity"]),
            deps=[],
            aggregate_fn=_aggregate_lexical_diversity,
        ),
        AggregationEntry(
            agg_id="transcript_output",
            selector=any_of(["transcript_output"]),
            deps=[],
            aggregate_fn=_aggregate_transcript_output_blob,
            output_type="blob",
        ),
        AggregationEntry(
            agg_id="simplified_transcript",
            selector=any_of(["simplified_transcript"]),
            deps=[],
            aggregate_fn=_aggregate_simplified_transcript,
        ),
        AggregationEntry(
            agg_id="pauses",
            selector=any_of(["pauses"]),
            deps=["acts"],
            aggregate_fn=_aggregate_pauses,
        ),
        AggregationEntry(
            agg_id="momentum",
            selector=any_of(["momentum"]),
            deps=["pauses"],
            aggregate_fn=_aggregate_momentum,
        ),
        AggregationEntry(
            agg_id="affect_tension",
            selector=any_of(["affect_tension"]),
            deps=["emotion", "sentiment"],
            aggregate_fn=_aggregate_affect_tension,
        ),
        AggregationEntry(
            agg_id="contagion",
            selector=any_of(["contagion"]),
            deps=["emotion"],
            aggregate_fn=_aggregate_contagion,
        ),
        AggregationEntry(
            agg_id="conversation_loops",
            selector=any_of(["conversation_loops"]),
            deps=[],
            aggregate_fn=_aggregate_conversation_loops,
        ),
        AggregationEntry(
            agg_id="temporal_dynamics",
            selector=any_of(["temporal_dynamics"]),
            deps=[],
            aggregate_fn=_aggregate_temporal_dynamics,
        ),
        AggregationEntry(
            agg_id="qa_analysis",
            selector=any_of(["qa_analysis"]),
            deps=["acts"],
            aggregate_fn=_aggregate_qa_analysis,
        ),
        AggregationEntry(
            agg_id="echoes",
            selector=any_of(["echoes"]),
            deps=[],
            aggregate_fn=_aggregate_echoes,
        ),
        AggregationEntry(
            agg_id="highlights",
            selector=any_of(["highlights"]),
            deps=[],
            aggregate_fn=_aggregate_highlights,
        ),
        AggregationEntry(
            agg_id="moments",
            selector=any_of(["moments"]),
            deps=["pauses", "echoes", "momentum", "qa_analysis"],
            aggregate_fn=_aggregate_moments,
        ),
        AggregationEntry(
            agg_id="summary",
            selector=any_of(["summary"]),
            deps=["highlights"],
            aggregate_fn=_aggregate_summary_blob,
            output_type="blob",
        ),
        AggregationEntry(
            agg_id="llm_summary",
            selector=any_of(["llm_summary"]),
            deps=[],
            aggregate_fn=aggregate_llm_summary_blob,
            output_type="blob",
        ),
        AggregationEntry(
            agg_id="narrative_summary",
            selector=any_of(["narrative_summary"]),
            deps=[],
            aggregate_fn=aggregate_narrative_summary_blob,
            output_type="blob",
        ),
        AggregationEntry(
            agg_id="llm_speaker_summary",
            selector=any_of(["llm_speaker_summary"]),
            deps=[],
            aggregate_fn=aggregate_llm_speaker_summary_group,
        ),
        AggregationEntry(
            agg_id="llm_action_items",
            selector=any_of(["llm_action_items"]),
            deps=[],
            aggregate_fn=aggregate_llm_action_items_group,
        ),
        AggregationEntry(
            agg_id="llm_custom_qa",
            selector=any_of(["llm_custom_qa"]),
            deps=[],
            # Disabled at registry until v2 aggregation is activation-enabled.
            aggregate_fn=_disabled_llm_custom_qa_group_agg,
        ),
        AggregationEntry(
            agg_id="insights",
            selector=any_of(["insights"]),
            deps=[],
            aggregate_fn=aggregate_insights_group,
        ),
        AggregationEntry(
            agg_id="semantic_similarity",
            selector=any_of(
                [
                    "semantic_similarity",
                ]
            ),
            deps=[],
            aggregate_fn=aggregate_semantic_similarity_group,
        ),
        AggregationEntry(
            agg_id="voice_mismatch",
            selector=any_of(["voice_mismatch"]),
            deps=[],
            aggregate_fn=aggregate_voice_mismatch_group,
        ),
        AggregationEntry(
            agg_id="voice_tension",
            selector=any_of(["voice_tension"]),
            deps=[],
            aggregate_fn=aggregate_voice_tension_group,
        ),
        AggregationEntry(
            agg_id="voice_fingerprint",
            selector=any_of(["voice_fingerprint"]),
            deps=[],
            aggregate_fn=aggregate_voice_fingerprint_group,
        ),
        AggregationEntry(
            agg_id="prosody",
            selector=any_of(
                ["voice_features", "voice_charts_core", "prosody_dashboard"]
            ),
            deps=[],
            aggregate_fn=_aggregate_prosody,
        ),
        AggregationEntry(
            agg_id="voice_contours",
            selector=any_of(["voice_contours"]),
            deps=[],
            aggregate_fn=_aggregate_voice_contours,
        ),
    ]
    return registry
