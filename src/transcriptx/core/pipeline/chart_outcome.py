"""
Whitelisted keys passed from group aggregation ``outcome`` into ``chart_outcome``.

Only base chart keys plus ``GROUP_CHART_OUTCOME_OPTIONAL_KEYS`` may appear on the
dict consumed by ``run_group_aggregate_charts``. Arbitrary aggregation blobs must
not leak into group chart generators.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet

# Frozen set of optional keys copied from aggregation outcome → chart_outcome.
# Add a key only in the same change set as the generator that consumes it.
GROUP_CHART_OUTCOME_OPTIONAL_KEYS: FrozenSet[str] = frozenset(
    {
        "ner_pooled",
        "entity_sentiment_pooled",
        "topic_modeling_pooled",
        "bertopic_pooled",
        "emotion_pooled",
        "tics_pooled",
        "epistemic_markers_pooled",
        "politeness_pooled",
        "stats_pooled",
        "interactions_pooled",
        "contagion_pooled",
        "transcript_quality_pooled",
        "topic_shift_pooled",
        "semantic_similarity_pooled",
        "keyphrases_pooled",
        "cohort_summaries",
    }
)

CHART_OUTCOME_BASE_KEYS: FrozenSet[str] = frozenset(
    {
        "session_rows",
        "speaker_rows",
        "metrics_spec",
        "content_rows",
        "content_rows_name",
    }
)


def merge_optional_chart_outcome_keys(
    chart_outcome: Dict[str, Any], outcome: Dict[str, Any]
) -> None:
    """Copy allowlisted optional keys from ``outcome`` into ``chart_outcome`` in place."""
    for key in GROUP_CHART_OUTCOME_OPTIONAL_KEYS:
        if key in outcome:
            chart_outcome[key] = outcome[key]
