"""Tests for web analysis module UI grouping and ordering."""

from transcriptx.core.pipeline.module_registry_specs import MODULE_CLASS_MAP
from transcriptx.web.module_option_format import format_module_option
from transcriptx.web.module_ui_groups import (
    flattened_spec_module_ids,
    group_modules_for_ui,
    module_sort_key,
    order_module_ids,
    order_strings_like_modules,
)

# Drift detector: update this tuple when intentionally changing MODULE_UI_GROUPS order/content.
EXPECTED_PINNED_SPEC_ORDER: tuple[str, ...] = (
    "stats",
    "transcript_output",
    "simplified_transcript",
    "tics",
    "pauses",
    "temporal_dynamics",
    "insight_eligibility",
    "sentiment",
    "emotion",
    "ner",
    "entity_sentiment",
    "topic_modeling",
    "semantic_similarity",
    "semantic_similarity_advanced",
    "semantic_similarity_v2",
    "understandability",
    "lexical_diversity",
    "acts",
    "interactions",
    "conversation_loops",
    "qa_analysis",
    "echoes",
    "contagion",
    "momentum",
    "moments",
    "affect_tension",
    "highlights",
    "summary",
    "llm_action_items",
    "insights",
    "voice_features",
    "voice_mismatch",
    "voice_tension",
    "voice_fingerprint",
    "voice_charts_core",
    "voice_contours",
    "prosody_dashboard",
    "wordclouds",
)


def test_flattened_spec_matches_pinned_order() -> None:
    assert flattened_spec_module_ids() == EXPECTED_PINNED_SPEC_ORDER


def test_spec_module_ids_are_registry_keys() -> None:
    for mid in flattened_spec_module_ids():
        assert mid in MODULE_CLASS_MAP, f"missing from MODULE_CLASS_MAP: {mid}"


def test_order_module_ids_known_then_unknown_alpha() -> None:
    out = order_module_ids(["zebra_unknown", "stats", "emotion", "aaa_unknown"])
    assert out[:2] == ["stats", "emotion"]
    assert out[2:] == ["aaa_unknown", "zebra_unknown"]


def test_order_module_ids_ignores_none_and_empty() -> None:
    out = order_module_ids(["stats", None, "", "emotion"])  # type: ignore[list-item]
    assert out == ["stats", "emotion"]


def test_group_modules_for_ui_str_only_ignores_none() -> None:
    groups = group_modules_for_ui(["emotion", None, "stats"])  # type: ignore[list-item]
    titles = [t for t, _ in groups]
    assert "Foundations" in titles
    assert "Language & Meaning" in titles
    flat = [m for _, ids in groups for m in ids]
    assert flat == ["stats", "emotion"]


def test_group_modules_for_ui_no_other_bucket_for_unknown() -> None:
    groups = group_modules_for_ui(["stats", "unknown_mod"])
    assert len(groups) == 1
    assert groups[0][1] == ["stats"]


def test_module_sort_key_tiers() -> None:
    assert module_sort_key("stats") < module_sort_key("aaa_unknown")
    assert module_sort_key("aaa_unknown") < module_sort_key(None)
    assert module_sort_key("aaa_unknown") < module_sort_key("other")
    assert module_sort_key("other") == module_sort_key("Other")


def test_order_strings_like_modules_sentinel_last() -> None:
    out = order_strings_like_modules(["Other", "sentiment", "zebra"])
    assert out[0] == "sentiment"
    assert out[1] == "zebra"
    assert out[2] == "Other"


def test_format_module_option_known_vs_unknown() -> None:
    known = format_module_option("stats")
    assert known.startswith("Foundations ·")
    unknown = format_module_option("not_a_real_module_id_zzz")
    assert unknown.startswith("Other ·")
