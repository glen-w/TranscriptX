"""Test-only flat AnalysisConfig field→pilot ownership map (before Step 1.4)."""

from __future__ import annotations

from transcriptx.core.config.pydantic_bridge import PYDANTIC_REGISTRY_PILOTS

_PARTIAL_PREFIX = "analysis_"


def _partial_pilot_field_map() -> dict[str, frozenset[str]]:
    out: dict[str, frozenset[str]] = {}
    for spec in PYDANTIC_REGISTRY_PILOTS:
        if not spec.pilot_id.startswith(_PARTIAL_PREFIX):
            continue
        out[spec.pilot_id] = frozenset(spec.model.model_fields.keys())
    return out


def test_flat_analysis_pilots_are_disjoint_and_complete() -> None:
    field_map = _partial_pilot_field_map()
    expected_ids = {
        "analysis_sentiment",
        "analysis_ner",
        "analysis_wordcloud",
        "analysis_interaction",
        "analysis_entity",
        "analysis_legacy_semantic",
    }
    assert set(field_map) == expected_ids

    seen: dict[str, str] = {}
    for pilot_id, names in sorted(field_map.items()):
        assert names, f"{pilot_id} has no fields"
        for name in names:
            if name in seen:
                raise AssertionError(
                    f"field {name!r} owned by both {seen[name]!r} and {pilot_id!r}"
                )
            seen[name] = pilot_id

    # Expected exact field lists from ownership-collapse plan.
    assert field_map["analysis_sentiment"] == frozenset(
        {
            "sentiment_window_size",
            "sentiment_min_confidence",
            "emotion_min_confidence",
            "emotion_model_name",
            "emotion_output_mode",
            "emotion_score_threshold",
            "sentiment_backend",
            "sentiment_model_name",
        }
    )
    assert field_map["analysis_ner"] == frozenset(
        {
            "ner_labels",
            "ner_min_confidence",
            "ner_include_geocoding",
            "ner_use_light_model",
            "ner_max_segments",
            "ner_batch_size",
        }
    )
    assert field_map["analysis_wordcloud"] == frozenset(
        {
            "wordcloud_max_words",
            "wordcloud_min_font_size",
            "wordcloud_stopwords",
            "exclude_unidentified_from_speaker_charts",
            "readability_metrics",
        }
    )
    assert field_map["analysis_interaction"] == frozenset(
        {
            "interaction_overlap_threshold",
            "interaction_min_gap",
            "interaction_min_segment_length",
            "interaction_response_threshold",
            "interaction_include_responses",
            "interaction_include_overlaps",
            "interaction_min_interactions",
            "interaction_time_window",
            "loop_max_intermediate_turns",
            "loop_exclude_monologues",
            "loop_min_gap",
            "loop_max_gap",
        }
    )
    assert field_map["analysis_entity"] == frozenset(
        {
            "entity_min_mentions",
            "entity_types",
            "entity_sentiment_threshold",
        }
    )
    assert len(field_map["analysis_legacy_semantic"]) == 25
    assert len(seen) == 8 + 6 + 5 + 12 + 3 + 25


def test_dashboard_display_and_overview_fields_are_disjoint() -> None:
    display = next(
        s for s in PYDANTIC_REGISTRY_PILOTS if s.pilot_id == "dashboard_display"
    )
    overview = next(
        s for s in PYDANTIC_REGISTRY_PILOTS if s.pilot_id == "dashboard_overview"
    )
    d_fields = set(display.model.model_fields)
    o_fields = set(overview.model.model_fields)
    overlap = d_fields & o_fields
    assert not overlap, f"dashboard pilot field overlap: {overlap}"
