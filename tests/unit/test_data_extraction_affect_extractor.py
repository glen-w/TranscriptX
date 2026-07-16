"""Offline unit tests for data_extraction.emotion_extractor (filename avoids auto-marker)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from transcriptx.core.data_extraction.emotion_extractor import EmotionDataExtractor
from transcriptx.core.data_extraction.validation import DataValidationError


@pytest.fixture
def extractor() -> EmotionDataExtractor:
    return EmotionDataExtractor()


@pytest.mark.unit
def test_extract_data_casts_speaker_id(extractor: EmotionDataExtractor) -> None:
    with patch.object(
        extractor,
        "extract_speaker_data",
        return_value={"dominant_emotion": "joy"},
    ) as mocked:
        out = extractor.extract_data({}, "7")
        mocked.assert_called_once_with({}, speaker_id=7)
        assert out["dominant_emotion"] == "joy"

    with patch.object(extractor, "extract_speaker_data", return_value={}) as mocked2:
        extractor.extract_data({}, "not-int")
        mocked2.assert_called_once_with({}, speaker_id="not-int")


@pytest.mark.unit
def test_extract_speaker_data_empty_and_full(extractor: EmotionDataExtractor) -> None:
    with patch.object(extractor, "get_speaker_segments", return_value=[]):
        empty = extractor.extract_speaker_data({}, speaker_id=1)
    assert empty["dominant_emotion"] is None
    assert empty["emotion_distribution"] == {}

    segments = [
        {
            "dominant_emotion": "joy",
            "emotion_scores": {"joy": 0.9, "sadness": 0.1},
        },
        {
            "dominant_emotion": "joy",
            "emotion_scores": {"joy": 0.8, "fear": 0.2},
        },
        {
            "dominant_emotion": "fear",
            "emotion_scores": {"fear": 0.7, "joy": 0.3},
        },
        {"dominant_emotion": None, "emotion_scores": "bad"},
    ]
    with patch.object(extractor, "get_speaker_segments", return_value=segments):
        data = extractor.extract_speaker_data({}, speaker_id=1)
    assert data["dominant_emotion"] == "joy"
    assert data["emotion_distribution"]["joy"] == pytest.approx(2 / 3)
    assert data["emotional_stability"] is not None
    assert data["emotion_transition_patterns"]["total_transitions"] == 2
    assert data["emotional_reactivity"] is not None
    assert data["emotion_consistency"] == pytest.approx(2 / 3)


@pytest.mark.unit
def test_validate_and_transform(extractor: EmotionDataExtractor) -> None:
    good = {
        "dominant_emotion": "joy",
        "emotion_distribution": {"joy": 1.0},
        "emotional_stability": 0.5,
        "emotion_transition_patterns": {},
        "emotional_reactivity": 0.2,
        "emotion_consistency": 0.8,
    }
    assert extractor.validate_data(good) is True
    transformed = extractor.transform_data(good)
    assert set(transformed.keys()) == {
        "dominant_emotion",
        "emotion_distribution",
        "emotional_stability",
        "emotion_transition_patterns",
        "emotional_reactivity",
        "emotion_consistency",
    }

    with patch(
        "transcriptx.core.data_extraction.emotion_extractor.validate_emotion_data",
        side_effect=DataValidationError("bad"),
    ):
        with pytest.raises(DataValidationError):
            extractor.validate_data({})


@pytest.mark.unit
def test_distribution_and_stability_edge_cases(extractor: EmotionDataExtractor) -> None:
    assert extractor._calculate_emotion_distribution([]) == {}
    assert extractor._calculate_emotional_stability([]) is None
    assert extractor._calculate_emotional_stability([{"joy": 0.0}]) is None
    assert (
        extractor._calculate_emotional_stability([{"joy": 0.0}, {"joy": 0.0}]) is None
    )
    stable = extractor._calculate_emotional_stability(
        [{"joy": 0.5, "sadness": 0.5}, {"joy": 0.5, "sadness": 0.5}]
    )
    assert stable is not None
    assert 0.0 <= stable <= 1.0


@pytest.mark.unit
def test_transition_reactivity_consistency_edges(
    extractor: EmotionDataExtractor,
) -> None:
    assert extractor._calculate_transition_patterns(["joy"]) == {}
    patterns = extractor._calculate_transition_patterns(["joy", "fear", "joy", "joy"])
    assert patterns["total_transitions"] == 3
    assert "transition_probabilities" in patterns
    assert patterns["transitions"]["joy"]["fear"] == 1

    assert extractor._calculate_emotional_reactivity([{"joy": 0.1}]) is None
    react = extractor._calculate_emotional_reactivity(
        [{"joy": 0.0, "fear": 1.0}, {"joy": 1.0, "fear": 0.0}]
    )
    assert react is not None
    assert 0.0 <= react <= 1.0

    assert extractor._calculate_emotion_consistency(["joy"]) is None
    assert extractor._calculate_emotion_consistency(
        ["joy", "joy", "fear"]
    ) == pytest.approx(2 / 3)


@pytest.mark.unit
def test_create_empty_emotion_data(extractor: EmotionDataExtractor) -> None:
    empty = extractor._create_empty_emotion_data()
    assert empty["dominant_emotion"] is None
    assert empty["emotion_distribution"] == {}
