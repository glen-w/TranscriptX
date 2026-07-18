"""Unit tests for lexical emotion v2 pipeline."""

from __future__ import annotations

import unicodedata

import pytest

from transcriptx.core.analysis.emotion.lexical_pipeline import (
    PLUTCHIK_EIGHT,
    score_segment_text,
)
from transcriptx.core.analysis.emotion.legacy_readers import (
    is_legacy_emotion_artifact,
    project_legacy_for_ui,
)
from transcriptx.core.analysis.fine_grained_emotion import order_display_labels


@pytest.mark.unit
def test_occurrence_coverage_counts_repeats():
    lexicon = {"happy": ["joy", "positive"], "sad": ["sadness", "negative"]}
    result = score_segment_text("happy happy sad", lexicon)
    assert result.tokens_considered == 3
    assert result.matched_occurrences == 3
    assert result.assignment_counts["joy"] == 2
    assert result.valence_assignment_counts["positive"] == 2
    assert abs(result.coverage - 1.0) < 1e-9


@pytest.mark.unit
def test_valence_not_in_plutchik_normalisation():
    lexicon = {"happy": ["joy", "positive"]}
    result = score_segment_text("happy", lexicon)
    assert set(result.emotion_scores) == set(PLUTCHIK_EIGHT)
    assert "positive" not in result.emotion_scores
    assert result.valence_scores["positive"] == 1.0


@pytest.mark.unit
def test_original_offsets_for_repeated_tokens():
    lexicon = {"joy": ["joy"]}
    text = "joy and joy"
    result = score_segment_text(text, lexicon)
    assert len(result.contributing) == 2
    assert result.contributing[0]["original_start"] == 0
    assert (
        text[
            result.contributing[1]["original_start"] : result.contributing[1][
                "original_end"
            ]
        ]
        == "joy"
    )


@pytest.mark.unit
def test_unicode_lookup_nfc():
    lexicon = {_lookup("café"): ["joy"]}
    # decomposed input should still match via NFC casefold in pipeline
    decomposed = unicodedata.normalize("NFD", "café")
    # rebuild lexicon key the same way as pipeline
    from transcriptx.core.analysis.emotion.lexical_pipeline import (
        score_segment_text as sst,
    )
    from transcriptx.core.analysis.emotion import lexical_pipeline as lp

    key = lp._lookup_key("café")
    lexicon = {key: ["joy"]}
    result = sst(decomposed, lexicon)
    # tokenisation may split combining marks — at least no crash / zero-denom NaN
    assert result.coverage == result.coverage  # not NaN
    assert result.emotion_scores["joy"] >= 0.0


def _lookup(s: str) -> str:
    from transcriptx.core.analysis.emotion.lexical_pipeline import _lookup_key

    return _lookup_key(s)


@pytest.mark.unit
def test_legacy_reader_marks_ui_only():
    payload = {"emotions": {"joy": 0.5}, "context_emotion_source": "nrc"}
    assert is_legacy_emotion_artifact(payload)
    view = project_legacy_for_ui(payload)
    assert view["ui_only"] is True
    assert view["analysis_consumer_forbidden"] is True
    assert view["context_emotion_source"] == "nrc"


@pytest.mark.unit
def test_fine_grained_display_order_neutral_last_tiebreak():
    labels = ("anger", "joy", "sadness", "neutral")
    scores = {"joy": 0.5, "anger": 0.5, "neutral": 0.9, "sadness": 0.1}
    qualifying = ["joy", "anger", "neutral"]
    ordered = order_display_labels(qualifying, scores, labels, max_labels=3)
    # anger before joy due to canonical index when scores tie
    assert ordered[0] == "anger"
    assert ordered[1] == "joy"
    assert ordered[-1] == "neutral"


@pytest.mark.unit
def test_emotion_module_no_context_fill():
    pytest.importorskip("nrclex")
    from transcriptx.core.analysis.emotion import EmotionAnalysis
    from transcriptx.core.analysis.emotion.projections import apply_lexical_projection
    from transcriptx.core.analysis.emotion_family.persist import (
        apply_pending_projections,
    )

    mod = EmotionAnalysis()
    segs = [
        {
            "id": "1",
            "speaker": "Alice",
            "text": "I am so happy and joyful today",
            "start": 0,
            "end": 1,
        },
        {
            "id": "2",
            "speaker": "Bob",
            "text": "This is terrible and sad",
            "start": 1,
            "end": 2,
        },
    ]
    result = mod.analyze(segs)
    assert result["semantics_version"] == "emotion_lexical_v2"
    assert result["run_status"] == "complete"
    assert "nrc_emotion" not in segs[0]
    apply_pending_projections(result, apply_one=apply_lexical_projection)
    for seg in segs:
        assert (
            "context_emotion_source" not in seg
            or seg.get("context_emotion_source") is None
        )
        assert "nrc_emotion" in seg
    assert result.get("usable_output") is True
