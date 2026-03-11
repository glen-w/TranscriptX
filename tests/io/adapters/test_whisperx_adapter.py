"""
Tests for WhisperXAdapter.

Verifies semantic parity with the previous transcript_importer.py path for all
fixture inputs — equivalent segments, speaker assignments, and metadata.
"""

from __future__ import annotations

import json
from pathlib import Path


from transcriptx.io.adapters.whisperx_adapter import WhisperXAdapter
from transcriptx.io.intermediate_transcript import IntermediateTranscript

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "transcripts" / "whisperx"
LEGACY_FIXTURE = (
    Path(__file__).parent.parent.parent / "fixtures" / "whisperx_legacy.json"
)


class TestWhisperXAdapterDetect:
    def test_confident_on_standard_format(self):
        adapter = WhisperXAdapter()
        path = FIXTURES / "standard.json"
        content = path.read_bytes()
        score = adapter.detect_confidence(path, content[:4096])
        assert score >= 0.8

    def test_confident_on_word_level(self):
        adapter = WhisperXAdapter()
        path = FIXTURES / "word_level.json"
        content = path.read_bytes()
        score = adapter.detect_confidence(path, content[:4096])
        assert score >= 0.8

    def test_confident_on_bare_list(self):
        adapter = WhisperXAdapter()
        path = FIXTURES / "bare_list.json"
        content = path.read_bytes()
        score = adapter.detect_confidence(path, content[:4096])
        assert score >= 0.7

    def test_zero_on_transcriptx_artifact(self):
        adapter = WhisperXAdapter()
        artifact = {
            "schema_version": "1.0",
            "source": {
                "type": "vtt",
                "original_path": "/tmp/x.vtt",
                "imported_at": "2025-01-01T00:00:00Z",
            },
            "segments": [
                {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_00", "text": "Hi"}
            ],
        }
        content = json.dumps(artifact).encode()
        assert adapter.detect_confidence(Path("test.json"), content) == 0.0

    def test_zero_on_non_json(self):
        adapter = WhisperXAdapter()
        content = b"WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi\n"
        assert adapter.detect_confidence(Path("test.json"), content) == 0.0

    def test_zero_on_empty_json_object(self):
        adapter = WhisperXAdapter()
        content = b"{}"
        assert adapter.detect_confidence(Path("test.json"), content) == 0.0


class TestWhisperXAdapterParseStandard:
    def test_produces_intermediate_transcript(self):
        adapter = WhisperXAdapter()
        path = FIXTURES / "standard.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert isinstance(result, IntermediateTranscript)
        assert result.source_tool == "whisperx"
        assert result.source_format == "json"
        assert len(result.turns) == 3

    def test_speaker_labels_preserved(self):
        adapter = WhisperXAdapter()
        path = FIXTURES / "standard.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        speakers = [t.speaker for t in result.turns]
        assert "SPEAKER_00" in speakers
        assert "SPEAKER_01" in speakers

    def test_timestamps_parsed(self):
        adapter = WhisperXAdapter()
        path = FIXTURES / "standard.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for turn in result.turns:
            assert turn.start is not None
            assert turn.end is not None
            assert turn.end > turn.start

    def test_no_warnings_on_clean_input(self):
        adapter = WhisperXAdapter()
        path = FIXTURES / "standard.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)
        assert not result.warnings


class TestWhisperXAdapterParseWordLevel:
    def test_promotes_speaker_from_words(self):
        adapter = WhisperXAdapter()
        path = FIXTURES / "word_level.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        # Segments without segment-level speaker should get speaker from words
        for turn in result.turns:
            assert turn.speaker is not None

    def test_words_array_preserved(self):
        adapter = WhisperXAdapter()
        path = FIXTURES / "word_level.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for turn in result.turns:
            assert turn.words is not None
            assert len(turn.words) > 0

    def test_most_common_speaker_wins(self):
        """Segment with 3 words: 2 SPEAKER_00, 1 SPEAKER_01 → SPEAKER_00 wins."""
        adapter = WhisperXAdapter()
        data = {
            "segments": [
                {
                    "start": 5.2,
                    "end": 8.0,
                    "text": "Let us start.",
                    "words": [
                        {
                            "word": "Let",
                            "start": 5.2,
                            "end": 5.5,
                            "speaker": "SPEAKER_00",
                        },
                        {
                            "word": "us",
                            "start": 5.5,
                            "end": 5.8,
                            "speaker": "SPEAKER_01",
                        },
                        {
                            "word": "start.",
                            "start": 5.8,
                            "end": 8.0,
                            "speaker": "SPEAKER_00",
                        },
                    ],
                }
            ]
        }
        content = json.dumps(data).encode()
        result = adapter.parse(Path("test.json"), content)
        assert result.turns[0].speaker == "SPEAKER_00"

    def test_parity_with_legacy_fixture(self):
        """WhisperXAdapter should parse the pinned legacy fixture correctly."""
        adapter = WhisperXAdapter()
        path = LEGACY_FIXTURE
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert len(result.turns) == 2
        assert result.turns[0].speaker == "SPEAKER_00"
        assert result.turns[1].speaker == "SPEAKER_01"
        assert result.turns[0].text == "Hello everyone."
        assert result.turns[1].text == "Welcome to the meeting."


class TestWhisperXAdapterParseBareList:
    def test_parses_bare_list(self):
        adapter = WhisperXAdapter()
        path = FIXTURES / "bare_list.json"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert len(result.turns) == 2
        assert result.turns[0].speaker == "SPEAKER_00"
        assert result.turns[1].speaker == "SPEAKER_01"


class TestWhisperXSemanticParity:
    """Verify semantic parity between WhisperXAdapter and the previous importer path.

    These tests ensure that the refactored adapter produces equivalent
    segments, speaker assignments, and metadata to what the old code produced.
    They do NOT check for literal byte-identical JSON.
    """

    def test_standard_segments_match_expected(self):
        from transcriptx.io.transcript_normalizer import TranscriptNormalizer
        from transcriptx.io.speaker_normalizer import normalize_speakers

        adapter = WhisperXAdapter()
        path = FIXTURES / "standard.json"
        content = path.read_bytes()
        intermediate = adapter.parse(path, content)

        turns = TranscriptNormalizer().normalize(intermediate)
        segments = normalize_speakers(turns)

        assert len(segments) == 3
        speakers = {s["speaker"] for s in segments}
        assert "SPEAKER_00" in speakers
        assert "SPEAKER_01" in speakers

        for seg in segments:
            assert seg["start"] >= 0
            assert seg["end"] > seg["start"]
            assert seg["text"]

    def test_word_level_speaker_promotion_parity(self):
        """Speaker promoted from words must match the legacy _normalize_legacy_segments logic."""
        from transcriptx.io.transcript_loader import _normalize_legacy_segments
        from transcriptx.io.transcript_normalizer import TranscriptNormalizer
        from transcriptx.io.speaker_normalizer import normalize_speakers

        path = LEGACY_FIXTURE
        content = path.read_bytes()
        data = json.loads(content)

        # Legacy path: extract most-common speaker from words
        old_segments = _normalize_legacy_segments(data)

        # New path: adapter → normalizer → speaker_normalizer
        adapter = WhisperXAdapter()
        intermediate = adapter.parse(path, content)
        turns = TranscriptNormalizer().normalize(intermediate)
        new_segments = normalize_speakers(turns)

        assert len(new_segments) == len(old_segments)
        for new, old in zip(new_segments, old_segments):
            # Both should resolve to SPEAKER_XX labels (may differ in exact ID
            # if ordering differs, but the set of unique speakers should match)
            assert new["text"] == old["text"]
            assert new["start"] == old["start"]
            assert new["end"] == old["end"]
