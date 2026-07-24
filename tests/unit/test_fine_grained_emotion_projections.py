"""Offline unit tests for fine_grained_emotion enriched-transcript projections."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.fine_grained_emotion import order_display_labels
from transcriptx.core.analysis.fine_grained_emotion.projections import (
    FAMILY_ONTOLOGY,
    FAMILY_ONTOLOGY_V1,
    FINE_GRAINED_PROJECTION_SEGMENT_FIELDS,
    apply_fine_grained_projection,
    clear_fine_grained_projection,
    display_families_for_labels,
    project_fine_grained_segment,
)


@pytest.mark.unit
def test_display_families_maps_known_and_unknown_labels():
    families = display_families_for_labels(
        ["joy", "anger", "curiosity", "neutral", "not_a_label"]
    )
    assert families["joy"] == "positive"
    assert families["anger"] == "negative"
    assert families["curiosity"] == "cognitive"
    assert families["neutral"] == "neutral"
    assert families["not_a_label"] == "other"


@pytest.mark.unit
def test_family_ontology_covers_goemotions_style_labels():
    # Ontology is display-only; keep a stable version id for fingerprinting.
    assert FAMILY_ONTOLOGY_V1 == "fine_grained_family_ontology_v1"
    assert "admiration" in FAMILY_ONTOLOGY
    assert FAMILY_ONTOLOGY["admiration"] == "positive"
    assert FAMILY_ONTOLOGY["grief"] == "negative"
    assert FAMILY_ONTOLOGY["surprise"] == "cognitive"


@pytest.mark.unit
def test_project_fine_grained_segment_shape_and_display_families():
    row = {
        "segment_id": "s1",
        "evaluation_state": "scored",
        "analytical_outcome": "mixed",
        "display_labels": ["joy", "anger"],
        "mixed": True,
        "qualifying_emotion_count": 2,
        "truncated": False,
        "scored_text_hash": "abc",
        "scores": {"joy": 0.8, "anger": 0.7},
    }
    proj = project_fine_grained_segment(
        row,
        artifact_generation_id="gen123",
        schema_version="fine_grained_transcriptx.emotion_result.v1",
    )
    assert proj["segment_id"] == "s1"
    assert proj["evaluation_state"] == "scored"
    assert proj["analytical_outcome"] == "mixed"
    assert proj["fine_grained_emotion_labels"] == ["joy", "anger"]
    assert proj["fine_grained_emotion_analytical_outcome"] == "mixed"
    assert proj["fine_grained_emotion_evaluation_state"] == "scored"
    assert proj["fine_grained_emotion_mixed"] is True
    assert proj["fine_grained_emotion_qualifying_emotion_count"] == 2
    assert proj["fine_grained_emotion_truncated"] is False
    assert proj["fine_grained_emotion_scored_text_hash"] == "abc"
    assert proj["fine_grained_emotion_families"] == {
        "joy": "positive",
        "anger": "negative",
    }
    ref = proj["fine_grained_emotion_canonical_ref"]
    assert ref["module_id"] == "fine_grained_emotion"
    assert ref["artifact_generation_id"] == "gen123"
    assert ref["schema_version"] == "fine_grained_transcriptx.emotion_result.v1"
    assert ref["semantics_version"] == "fine_grained_emotion_v1"
    assert ref["row_key"] == "s1"
    assert "integrity_checksum" in ref
    # Families are projection-time only — not expected on analytical rows.
    assert "fine_grained_emotion_families" not in row


@pytest.mark.unit
def test_project_fine_grained_segment_empty_display_defaults():
    row = {
        "segment_id": "empty-1",
        "evaluation_state": "empty",
        "display_labels": [],
        "scored_text_hash": "h",
    }
    proj = project_fine_grained_segment(
        row,
        artifact_generation_id="g",
        schema_version="fine_grained_transcriptx.emotion_result.v1",
    )
    assert proj["fine_grained_emotion_labels"] == []
    assert proj["fine_grained_emotion_families"] == {}
    assert proj["fine_grained_emotion_mixed"] is False
    assert proj["fine_grained_emotion_qualifying_emotion_count"] == 0
    assert proj["fine_grained_emotion_truncated"] is False


@pytest.mark.unit
def test_apply_and_clear_fine_grained_projection_roundtrip():
    seg = {
        "id": "s1",
        "text": "hello",
        "fine_grained_emotion_labels": ["stale"],
        "fine_grained_emotion_families": {"stale": "other"},
        "unrelated": 1,
    }
    proj = {
        "fine_grained_emotion_labels": ["joy"],
        "fine_grained_emotion_analytical_outcome": "labeled",
        "fine_grained_emotion_evaluation_state": "scored",
        "fine_grained_emotion_mixed": False,
        "fine_grained_emotion_qualifying_emotion_count": 1,
        "fine_grained_emotion_truncated": False,
        "fine_grained_emotion_scored_text_hash": "h",
        "fine_grained_emotion_canonical_ref": {"module_id": "fine_grained_emotion"},
        "fine_grained_emotion_families": {"joy": "positive"},
        # Non-owned keys must not be copied onto the segment.
        "segment_id": "s1",
        "evaluation_state": "scored",
    }
    apply_fine_grained_projection(seg, proj)
    for field in FINE_GRAINED_PROJECTION_SEGMENT_FIELDS:
        assert field in seg
    assert seg["fine_grained_emotion_labels"] == ["joy"]
    assert seg["fine_grained_emotion_families"] == {"joy": "positive"}
    assert seg["unrelated"] == 1
    assert seg["id"] == "s1"
    # apply copies only owned projection fields, not helper keys.
    assert "segment_id" not in seg
    assert "evaluation_state" not in seg

    clear_fine_grained_projection(seg)
    for field in FINE_GRAINED_PROJECTION_SEGMENT_FIELDS:
        assert field not in seg
    assert seg["unrelated"] == 1


@pytest.mark.unit
def test_order_display_labels_respects_cap_and_empty():
    labels = ("anger", "joy", "neutral")
    scores = {"anger": 0.9, "joy": 0.8, "neutral": 0.7}
    assert order_display_labels(["anger", "joy", "neutral"], scores, labels, 1) == [
        "anger"
    ]
    assert order_display_labels([], scores, labels, 3) == []
    assert order_display_labels(["neutral"], {"neutral": 0.5}, labels, 3) == ["neutral"]
    assert order_display_labels(["joy", "anger"], scores, labels, 0) == []
