"""Registry: agg_id -> generator object."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple

from transcriptx.core.analysis.group_charts.acts import ActsGroupChartGenerator
from transcriptx.core.analysis.group_charts.contagion_pooled_charts import (
    ContagionPooledGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.emotion_charts import (
    EmotionGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.entity_sentiment_pooled_charts import (
    EntitySentimentPooledGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.generic_field_allowlists import (
    allowed_numeric_keys_for_generic_agg,
)
from transcriptx.core.analysis.group_charts.generic_numeric import (
    GenericNumericGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.highlights_moments import (
    HighlightsGroupChartGenerator,
    MomentsGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.interactions_charts import (
    InteractionsGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.pauses_charts import (
    PausesGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.prosody_charts import (
    ProsodyGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.sentiment_charts import (
    SentimentGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.ner_pooled_charts import (
    NerPooledGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.stats_charts import StatsGroupChartGenerator
from transcriptx.core.analysis.group_charts.tics_group_charts import (
    TicsGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.transcript_quality_charts import (
    TranscriptQualityGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.topic_shift_charts import (
    TopicShiftGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.topic_modeling_group_charts import (
    TopicModelingGroupChartGenerator,
)
from transcriptx.core.analysis.group_charts.bertopic_group_charts import (
    BertopicGroupChartGenerator,
)


class GroupChartGenerator(Protocol):
    agg_id: str

    def can_generate(self, outcome: Dict[str, Any]) -> bool: ...

    def generate(self, ctx: Any, outcome: Dict[str, Any]) -> Optional[List[Any]]: ...


# Which chart families each registered agg may emit (documentation + future tooling).
GROUP_AGGREGATE_CHART_FAMILIES: Dict[str, Tuple[str, ...]] = {
    "acts": ("aggregate_pie_bar", "temporal_overlay", "pooled_single_view"),
    "stats": (
        "session_bars",
        "speaker_bars",
        "cross_session_speaker",
        "pooled_single_view",
    ),
    "sentiment": (
        "session_bars",
        "speaker_bars",
        "temporal_overlay",
        "cross_session_speaker",
    ),
    "highlights": ("session_bars",),
    "moments": ("session_bars",),
    "prosody": ("session_bars", "temporal_overlay"),
    "pauses": ("session_summary_bars", "temporal_overlay"),
    "conversation_loops": ("session_bars",),
    "emotion": ("session_bars", "temporal_overlay", "pooled_single_view"),
    "interactions": ("session_bars", "pooled_single_view"),
    "tics": ("session_bars", "pooled_single_view"),
    "transcript_quality": ("session_bars",),
    "topic_shift": ("session_bars", "temporal_overlay"),
    "understandability": ("session_bars",),
    "lexical_diversity": ("session_bars",),
    "simplified_transcript": ("session_bars",),
    "momentum": ("session_bars",),
    "affect_tension": ("session_bars",),
    "qa_analysis": ("session_bars",),
    "echoes": ("session_bars",),
    "ner": ("pooled_single_view",),
    "entity_sentiment": ("pooled_single_view",),
    "topic_modeling": ("pooled_single_view",),
    "bertopic": ("pooled_single_view",),
    "contagion": ("pooled_single_view",),
    "llm_action_items": ("session_bars",),
    "insights": ("session_bars",),
    "semantic_similarity": ("session_bars",),
    "voice_mismatch": ("session_bars",),
    "voice_tension": ("session_bars",),
    "voice_fingerprint": ("session_bars",),
}


def build_group_chart_registry() -> Dict[str, GroupChartGenerator]:
    """
    Generators for group row aggregations.

    Omitted: ``wordclouds`` (charts written by run_group_wordclouds), ``summary`` /
    ``llm_summary`` / ``narrative_summary`` (blob output), ``llm_speaker_summary``
    (speaker text rows; Data/Insights only), ``insight_eligibility`` /
    ``voice_contours`` (session data rows only), ``transcript_output`` (blob index).

    ``ner``, ``entity_sentiment``, ``topic_modeling``, ``interactions`` (composite),
    and ``contagion`` (pooled-only) use dedicated or composite generators for
    ``pooled_single_view`` where applicable.
    ``temporal_dynamics`` remains omitted from this registry.

    Field-level allowlists for generic numerics live in
    ``generic_field_allowlists.py``; outcomes in
    ``docs/groups/group_charts_phase4_outcome_table.md``.
    """
    generic_ids = (
        "understandability",
        "lexical_diversity",
        "simplified_transcript",
        "momentum",
        "affect_tension",
        "qa_analysis",
        "echoes",
        "llm_action_items",
        "insights",
        "semantic_similarity",
        "voice_mismatch",
        "voice_tension",
        "voice_fingerprint",
    )
    reg: Dict[str, GroupChartGenerator] = {
        "acts": ActsGroupChartGenerator(),
        "stats": StatsGroupChartGenerator(),
        "sentiment": SentimentGroupChartGenerator(),
        "highlights": HighlightsGroupChartGenerator(),
        "moments": MomentsGroupChartGenerator(),
        "prosody": ProsodyGroupChartGenerator(),
        "pauses": PausesGroupChartGenerator(),
        "conversation_loops": GenericNumericGroupChartGenerator(
            "conversation_loops",
            flatten_nested=True,
            max_charts=10,
            allowed_numeric_keys=allowed_numeric_keys_for_generic_agg(
                "conversation_loops"
            ),
        ),
        "emotion": EmotionGroupChartGenerator(),
        "interactions": InteractionsGroupChartGenerator(),
        "contagion": ContagionPooledGroupChartGenerator(),
        "ner": NerPooledGroupChartGenerator(),
        "entity_sentiment": EntitySentimentPooledGroupChartGenerator(),
        "topic_modeling": TopicModelingGroupChartGenerator(),
        "bertopic": BertopicGroupChartGenerator(),
        "tics": TicsGroupChartGenerator(),
        "transcript_quality": TranscriptQualityGroupChartGenerator(),
        "topic_shift": TopicShiftGroupChartGenerator(),
    }
    for aid in generic_ids:
        reg[aid] = GenericNumericGroupChartGenerator(
            aid,
            flatten_nested=True,
            max_charts=10,
            allowed_numeric_keys=allowed_numeric_keys_for_generic_agg(aid),
        )
    return reg


GROUP_CHART_REGISTRY: Dict[str, GroupChartGenerator] = build_group_chart_registry()
