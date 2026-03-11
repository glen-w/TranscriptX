"""
Tests for TranscriptNormalizer.
"""

from __future__ import annotations

from transcriptx.io.intermediate_transcript import (
    IntermediateTurn,
    IntermediateTranscript,
)
from transcriptx.io.transcript_normalizer import TranscriptNormalizer


def _make_transcript(*turns: IntermediateTurn) -> IntermediateTranscript:
    return IntermediateTranscript(
        source_tool="test",
        source_format="json",
        turns=list(turns),
        source_metadata={},
        warnings=[],
    )


def _turn(
    text="Hello",
    speaker=None,
    start=0.0,
    end=1.0,
    index=0,
    raw_turn_id=None,
):
    return IntermediateTurn(
        text=text,
        speaker=speaker,
        start=start,
        end=end,
        turn_index=index,
        raw_turn_id=raw_turn_id,
    )


class TestEndTimestampRepair:
    def test_fills_missing_end_from_next_start(self):
        t0 = IntermediateTurn(
            text="Hi", speaker=None, start=0.0, end=None, turn_index=0
        )
        t1 = IntermediateTurn(
            text="There", speaker=None, start=2.5, end=4.0, turn_index=1
        )
        transcript = _make_transcript(t0, t1)

        normalizer = TranscriptNormalizer()
        turns = normalizer.normalize(transcript)

        assert turns[0].end == 2.5

    def test_fills_missing_end_with_estimate_when_last(self):
        t0 = IntermediateTurn(text="Hi", speaker=None, start=0.0, end=2.0, turn_index=0)
        t1 = IntermediateTurn(
            text="Bye", speaker=None, start=3.0, end=None, turn_index=1
        )
        transcript = _make_transcript(t0, t1)

        normalizer = TranscriptNormalizer()
        turns = normalizer.normalize(transcript)

        # Should be start + estimated duration (median of known = 2.0s)
        assert turns[1].end == pytest.approx(3.0 + 2.0, abs=0.01)

    def test_no_repair_when_end_present(self):
        t = _turn(start=1.0, end=3.0)
        transcript = _make_transcript(t)

        normalizer = TranscriptNormalizer()
        turns = normalizer.normalize(transcript)

        assert turns[0].end == 3.0

    def test_warns_on_repaired_ends(self):
        t = IntermediateTurn(text="Hi", speaker=None, start=0.0, end=None, turn_index=0)
        transcript = _make_transcript(t)

        normalizer = TranscriptNormalizer()
        normalizer.normalize(transcript)

        assert any("estimated" in w for w in transcript.warnings)


class TestSpeakerLabelCleaning:
    def test_strips_trailing_colon(self):
        t = _turn(speaker="Alice:")
        transcript = _make_transcript(t)
        turns = TranscriptNormalizer().normalize(transcript)
        assert turns[0].speaker == "Alice"

    def test_strips_embedded_timestamp(self):
        t = _turn(speaker="Bob [00:01:23]")
        transcript = _make_transcript(t)
        turns = TranscriptNormalizer().normalize(transcript)
        assert turns[0].speaker == "Bob"

    def test_unknown_speaker_becomes_none(self):
        t = _turn(speaker="Unknown Speaker")
        transcript = _make_transcript(t)
        turns = TranscriptNormalizer().normalize(transcript)
        assert turns[0].speaker is None

    def test_none_speaker_unchanged(self):
        t = _turn(speaker=None)
        transcript = _make_transcript(t)
        turns = TranscriptNormalizer().normalize(transcript)
        assert turns[0].speaker is None

    def test_normal_speaker_unchanged(self):
        t = _turn(speaker="SPEAKER_00")
        transcript = _make_transcript(t)
        turns = TranscriptNormalizer().normalize(transcript)
        assert turns[0].speaker == "SPEAKER_00"


class TestOverlapGapWarnings:
    def test_warns_on_overlap(self):
        t0 = _turn(text="A", start=0.0, end=3.0, index=0)
        t1 = _turn(text="B", start=1.0, end=4.0, index=1)
        transcript = _make_transcript(t0, t1)

        normalizer = TranscriptNormalizer()
        normalizer.normalize(transcript)

        assert any("overlap" in w.lower() for w in transcript.warnings)

    def test_warns_on_large_gap(self):
        t0 = _turn(text="A", start=0.0, end=1.0, index=0)
        t1 = _turn(text="B", start=60.0, end=62.0, index=1)
        transcript = _make_transcript(t0, t1)

        normalizer = TranscriptNormalizer(gap_warning_threshold_s=10.0)
        normalizer.normalize(transcript)

        assert any("gap" in w.lower() for w in transcript.warnings)

    def test_no_warning_on_normal_gap(self):
        t0 = _turn(text="A", start=0.0, end=1.0, index=0)
        t1 = _turn(text="B", start=1.5, end=3.0, index=1)
        transcript = _make_transcript(t0, t1)

        normalizer = TranscriptNormalizer(gap_warning_threshold_s=30.0)
        normalizer.normalize(transcript)

        assert not any("gap" in w.lower() for w in transcript.warnings)


class TestSameSpeakerMerge:
    def test_merges_consecutive_same_speaker(self):
        t0 = _turn(text="Hello", speaker="Alice", start=0.0, end=1.0, index=0)
        t1 = _turn(text="World", speaker="Alice", start=1.0, end=2.0, index=1)
        transcript = _make_transcript(t0, t1)

        normalizer = TranscriptNormalizer(merge_same_speaker=True)
        turns = normalizer.normalize(transcript)

        assert len(turns) == 1
        assert turns[0].text == "Hello World"
        assert turns[0].end == 2.0

    def test_does_not_merge_different_speakers(self):
        t0 = _turn(text="Hello", speaker="Alice", start=0.0, end=1.0, index=0)
        t1 = _turn(text="Hi", speaker="Bob", start=1.0, end=2.0, index=1)
        transcript = _make_transcript(t0, t1)

        normalizer = TranscriptNormalizer(merge_same_speaker=True)
        turns = normalizer.normalize(transcript)

        assert len(turns) == 2

    def test_merge_disabled_by_default(self):
        t0 = _turn(text="Hello", speaker="Alice", start=0.0, end=1.0, index=0)
        t1 = _turn(text="World", speaker="Alice", start=1.0, end=2.0, index=1)
        transcript = _make_transcript(t0, t1)

        normalizer = TranscriptNormalizer()  # default: merge_same_speaker=False
        turns = normalizer.normalize(transcript)

        assert len(turns) == 2


import pytest
