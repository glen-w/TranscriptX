"""Offline tests for insight eligibility phrase quality gate and scoring."""

from __future__ import annotations

import pytest

pytest.importorskip("spacy")

pytestmark = pytest.mark.requires_nlp

from transcriptx.core.analysis.insight_eligibility.content_scoring import (
    score_content_phrases,
)
from transcriptx.core.analysis.insight_eligibility.phrase_extraction import (
    _passes_phrase_quality_gate,
    _phrase_quality_from_result,
    extract_content_phrases,
)
from transcriptx.core.analysis.phrase_quality.analyser import (
    analyse_phrase,
    annotations_from_surfaces,
)
from transcriptx.core.analysis.phrase_quality.types import WEAK_BARE_NOUN


def test_passes_phrase_quality_gate_rejects_fillers_and_high_stopword_ratio() -> None:
    assert _passes_phrase_quality_gate([], set()) is False
    assert (
        _passes_phrase_quality_gate(
            [("of", "ADP"), ("course", "NOUN")],
            set(),
        )
        is False
    )
    assert (
        _passes_phrase_quality_gate(
            [("budget", "NOUN"), ("risk", "NOUN")],
            set(),
        )
        is True
    )
    # High stopword ratio gate.
    assert (
        _passes_phrase_quality_gate(
            [("the", "DET"), ("of", "ADP"), ("budget", "NOUN")],
            set(),
            stopword_ratio_threshold=0.3,
        )
        is False
    )


def test_phrase_quality_from_result_pos_weights() -> None:
    noun = analyse_phrase(
        annotations_from_surfaces(["budget", "risk"], pos_tags=["NOUN", "NOUN"])
    )
    verb = analyse_phrase(annotations_from_surfaces(["deliver"], pos_tags=["VERB"]))
    other = analyse_phrase(annotations_from_surfaces(["quick"], pos_tags=["ADJ"]))
    assert _phrase_quality_from_result(noun)["pos_weight"] == 1.0
    assert _phrase_quality_from_result(verb)["pos_weight"] == 0.9
    assert _phrase_quality_from_result(other)["pos_weight"] == 0.7


def test_score_content_phrases_string_rows_entities_and_soft_penalties() -> None:
    scores = score_content_phrases(
        [
            "battery storage",
            {
                "phrase": "the war",
                "quality": {
                    "stopword_ratio": 0.5,
                    "content_token_ratio": 0.5,
                    "pos_weight": 1.0,
                    "penalties": [WEAK_BARE_NOUN],
                },
            },
            "",
        ],
        windows=[{"text": "battery storage planning"}],
        speaker_blocks=[{"text": "battery storage"}],
        entities=["battery storage"],
    )
    assert "battery storage" in scores
    assert scores["battery storage"]["entity_linkage"] == 1.0
    assert scores["the war"]["soft_penalty"] > 0.0


def test_extract_content_phrases_empty_and_min_score() -> None:
    rows, scores = extract_content_phrases(
        [],
        tic_mask=set(),
        windows=[],
        speaker_blocks=[],
    )
    assert rows == []
    assert scores == {}
