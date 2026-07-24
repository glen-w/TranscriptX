"""Tests for whitelisted optional keys on group chart_outcome."""

from __future__ import annotations

from transcriptx.core.pipeline.chart_outcome import (
    GROUP_CHART_OUTCOME_OPTIONAL_KEYS,
    merge_optional_chart_outcome_keys,
)


def test_merge_optional_only_allowlisted_keys() -> None:
    chart_outcome = {
        "session_rows": [{"order_index": 0}],
        "speaker_rows": [],
        "metrics_spec": None,
        "content_rows": None,
        "content_rows_name": None,
    }
    outcome = {
        **chart_outcome,
        "mentions_index": {"opaque": True},
        "blob_payload": {"should_not": "leak"},
        "ner_pooled": {"schema_version": 1, "entity_type_counts": {"PER": 2}},
    }
    merge_optional_chart_outcome_keys(chart_outcome, outcome)
    assert "mentions_index" not in chart_outcome
    assert "blob_payload" not in chart_outcome
    assert chart_outcome.get("ner_pooled") == outcome["ner_pooled"]


def test_optional_keys_constant_is_frozen_subset() -> None:
    assert "ner_pooled" in GROUP_CHART_OUTCOME_OPTIONAL_KEYS
    assert "entity_sentiment_pooled" in GROUP_CHART_OUTCOME_OPTIONAL_KEYS
    assert "interactions_pooled" in GROUP_CHART_OUTCOME_OPTIONAL_KEYS
    assert "contagion_pooled" in GROUP_CHART_OUTCOME_OPTIONAL_KEYS
    assert "transcript_quality_pooled" in GROUP_CHART_OUTCOME_OPTIONAL_KEYS
    assert "epistemic_markers_pooled" in GROUP_CHART_OUTCOME_OPTIONAL_KEYS
    assert "politeness_pooled" in GROUP_CHART_OUTCOME_OPTIONAL_KEYS
    assert "semantic_similarity_pooled" in GROUP_CHART_OUTCOME_OPTIONAL_KEYS
    assert "topic_shift_pooled" in GROUP_CHART_OUTCOME_OPTIONAL_KEYS
    assert "mentions_index" not in GROUP_CHART_OUTCOME_OPTIONAL_KEYS
