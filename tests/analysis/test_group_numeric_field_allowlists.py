"""Contract tests for generic numeric session field allowlists (Phase 4 curation).

File name avoids ``*generic*`` under ``tests/analysis/``: conftest path heuristics
treat any path containing the substring ``ner`` as model-heavy (false positive on
``generic``).
"""

from __future__ import annotations

from transcriptx.core.analysis.group_charts.generic_field_allowlists import (
    GENERIC_SESSION_FIELD_ALLOWLISTS,
    allowed_numeric_keys_for_generic_agg,
)
from transcriptx.core.analysis.group_charts.registry import build_group_chart_registry


def test_allowed_numeric_keys_unknown_agg_returns_none() -> None:
    assert allowed_numeric_keys_for_generic_agg("not_a_real_agg") is None


def test_emotion_uses_open_numeric_set() -> None:
    """emotion is registered generically but not field-curated in the allowlist map."""
    assert "emotion" not in GENERIC_SESSION_FIELD_ALLOWLISTS
    assert allowed_numeric_keys_for_generic_agg("emotion") is None


def test_allowlist_map_keys_match_curated_generic_aggs() -> None:
    expected = frozenset(
        {
            "conversation_loops",
            "interactions",
            "qa_analysis",
            "echoes",
            "momentum",
            "affect_tension",
            "understandability",
            "tics",
            "lexical_diversity",
        }
    )
    assert frozenset(GENERIC_SESSION_FIELD_ALLOWLISTS.keys()) == expected


def test_echoes_allowlist_includes_nested_counts_by_kind() -> None:
    keys = allowed_numeric_keys_for_generic_agg("echoes")
    assert keys is not None
    assert "total_events" in keys
    assert "counts_by_kind.echo" in keys
    assert "counts_by_kind.paraphrase" in keys
    assert "counts_by_kind.explicit_quote" in keys


def test_registry_generators_use_same_allowlists_as_map() -> None:
    reg = build_group_chart_registry()
    for agg_id, gen in reg.items():
        allow = getattr(gen, "allowed_numeric_keys", None)
        if allow is None:
            continue
        expected = allowed_numeric_keys_for_generic_agg(agg_id)
        assert (
            expected is not None
        ), f"{agg_id} has generator allowlist but no map entry"
        assert allow == expected
