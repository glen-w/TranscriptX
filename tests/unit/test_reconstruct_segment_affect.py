"""Unit tests for contagion emotion reconstruction."""

from __future__ import annotations

import logging

import pytest

from transcriptx.core.analysis.contagion.emotion_reconstruction import (
    reconstruct_emotion_data,
)


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("test.contagion.emotion_reconstruction")


@pytest.mark.unit
def test_reconstruct_from_contextual_all(logger: logging.Logger) -> None:
    segs = [
        {"speaker": "Alice", "text": "I am happy today"},
        {"speaker": "Alice", "text": "Still feeling great"},
        {"speaker": "Bob", "text": "I am sad"},
        {"speaker": "Alice", "text": ""},
    ]
    out, field, ok = reconstruct_emotion_data(
        segs,
        {"contextual_all": {"Alice": ["joy", "trust"], "Bob": ["sadness"]}},
        logger,
    )
    assert ok is True
    assert field == "context_emotion"
    assert out[0]["context_emotion"] == "joy"
    assert out[1]["context_emotion"] == "trust"
    assert out[2]["context_emotion"] == "sadness"
    assert "context_emotion" not in out[3]


@pytest.mark.unit
def test_reconstruct_from_contextual_examples_prefers_higher_score(
    logger: logging.Logger,
) -> None:
    segs = [{"speaker": "Alice", "text": "I am happy today"}]
    out, field, ok = reconstruct_emotion_data(
        segs,
        {
            "contextual_examples": {
                "Alice": {
                    "joy": [(0.4, "I am happy today"), (0.95, "I am happy today")],
                    "anger": [(0.2, "other text")],
                }
            }
        },
        logger,
    )
    assert ok is True
    assert field == "context_emotion"
    assert out[0]["context_emotion"] == "joy"


@pytest.mark.unit
def test_reconstruct_from_nrc_scores_fallback(logger: logging.Logger) -> None:
    segs = [{"speaker": "Alice", "text": "hello there"}]
    out, field, ok = reconstruct_emotion_data(
        segs,
        {"nrc_scores": {"Alice": {"joy": 0.5, "anger": 0.0}}},
        logger,
    )
    assert ok is True
    assert field == "nrc_emotion"
    assert out[0]["nrc_emotion"]["joy"] == 0.5


@pytest.mark.unit
def test_reconstruct_fails_when_no_usable_emotion(logger: logging.Logger) -> None:
    segs = [{"speaker": "Alice", "text": "hello"}]
    out, field, ok = reconstruct_emotion_data(segs, {}, logger)
    assert out is segs
    assert field is None
    assert ok is False


@pytest.mark.unit
def test_reconstruct_skips_all_zero_nrc(logger: logging.Logger) -> None:
    segs = [{"speaker": "Alice", "text": "hello"}]
    _out, field, ok = reconstruct_emotion_data(
        segs,
        {"nrc_scores": {"Alice": {"joy": 0.0, "anger": 0.0}}},
        logger,
    )
    assert field is None
    assert ok is False
