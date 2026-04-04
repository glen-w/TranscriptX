"""
Tests for GenericDiarisedTextAdapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.io.adapters.generic_diarised_text_adapter import (
    GenericDiarisedTextAdapter,
)
from transcriptx.io.intermediate_transcript import IntermediateTranscript

FIXTURES = (
    Path(__file__).parent.parent.parent / "fixtures" / "transcripts" / "generic_text"
)


class TestGenericAdapterDetect:
    def test_confident_on_speaker_colon_text(self):
        adapter = GenericDiarisedTextAdapter()
        content = b"Alice: Hello everyone.\nBob: Hi there.\nAlice: Ready to begin?\n"
        assert adapter.detect_confidence(Path("test.txt"), content) >= 0.5

    def test_confident_on_timestamped_format(self):
        adapter = GenericDiarisedTextAdapter()
        content = b"00:00:01 Alice: Hello.\n00:00:05 Bob: Hi.\n"
        assert adapter.detect_confidence(Path("test.txt"), content) >= 0.5

    def test_low_on_non_diarised_text(self):
        adapter = GenericDiarisedTextAdapter()
        content = b"This is a plain text document.\nNo speakers here.\nJust prose.\n"
        score = adapter.detect_confidence(Path("test.txt"), content)
        assert score < 0.3

    def test_zero_on_binary_content(self):
        adapter = GenericDiarisedTextAdapter()
        content = b"\x00\x01\x02\x03\x04\xff\xfe\xfd" * 100  # clearly binary
        assert adapter.detect_confidence(Path("test.bin"), content) == 0.0

    def test_zero_on_null_bytes(self):
        adapter = GenericDiarisedTextAdapter()
        content = b"Alice: Hello\x00there.\nBob: Hi.\n"
        assert adapter.detect_confidence(Path("test.txt"), content) == 0.0

    def test_confident_on_simple_fixture(self):
        adapter = GenericDiarisedTextAdapter()
        path = FIXTURES / "simple.txt"
        content = path.read_bytes()
        assert adapter.detect_confidence(path, content) >= 0.5


class TestGenericAdapterParseSimple:
    def test_produces_intermediate_transcript(self):
        adapter = GenericDiarisedTextAdapter()
        path = FIXTURES / "simple.txt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert isinstance(result, IntermediateTranscript)
        assert result.source_tool == "generic_text"
        assert result.source_format == "txt"
        assert len(result.turns) == 4

    def test_speaker_names_extracted(self):
        adapter = GenericDiarisedTextAdapter()
        path = FIXTURES / "simple.txt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        speakers = [t.speaker for t in result.turns]
        assert "Alice" in speakers
        assert "Bob" in speakers

    def test_no_timestamps_in_simple_format(self):
        adapter = GenericDiarisedTextAdapter()
        path = FIXTURES / "simple.txt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for turn in result.turns:
            assert turn.start is None
            assert turn.end is None

    def test_turn_index_sequential(self):
        adapter = GenericDiarisedTextAdapter()
        path = FIXTURES / "simple.txt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for i, turn in enumerate(result.turns):
            assert turn.turn_index == i


class TestGenericAdapterParseWithTimestamps:
    def test_timestamps_extracted(self):
        adapter = GenericDiarisedTextAdapter()
        path = FIXTURES / "with_timestamps.txt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        assert len(result.turns) == 4
        assert result.turns[0].start == pytest.approx(1.0)
        assert result.turns[1].start == pytest.approx(5.0)
        assert result.turns[2].start == pytest.approx(12.0)

    def test_end_timestamps_are_none(self):
        adapter = GenericDiarisedTextAdapter()
        path = FIXTURES / "with_timestamps.txt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        for turn in result.turns:
            assert turn.end is None


class TestGenericAdapterPreambleRemoval:
    def test_skips_preamble_before_first_turn(self):
        adapter = GenericDiarisedTextAdapter()
        path = FIXTURES / "with_preamble.txt"
        content = path.read_bytes()
        result = adapter.parse(path, content)

        # Should only have 4 diarised turns, not the preamble lines
        assert len(result.turns) == 4
        speakers = {t.speaker for t in result.turns}
        assert "Alice" in speakers
        assert "Bob" in speakers

    def test_inline_content(self):
        """Inline test without fixtures.

        The preamble uses lines that cannot match the speaker-colon-text
        pattern (no capital-letter-prefixed colon-separated lines), so they
        are correctly skipped before the first diarised turn.
        """
        adapter = GenericDiarisedTextAdapter()
        content = (
            b"=== Q1 Review Meeting ===\n"
            b"2025-01-15\n"
            b"\n"
            b"Alice: Good morning.\n"
            b"Bob: Good morning Alice.\n"
        )
        result = adapter.parse(Path("test.txt"), content)
        assert len(result.turns) == 2

    def test_empty_file_produces_warning(self):
        adapter = GenericDiarisedTextAdapter()
        result = adapter.parse(Path("empty.txt"), b"")
        assert any("no diarised turns" in w.lower() for w in result.warnings)


class TestGenericAdapterBinaryGuard:
    def test_binary_content_refused(self):
        adapter = GenericDiarisedTextAdapter()
        binary = b"PK\x03\x04" + b"\x00" * 100  # ZIP/DOCX magic bytes
        result = adapter.parse(Path("mystery.docx"), binary)
        assert len(result.turns) == 0
        assert any(
            "not appear to be text" in w or "refusing" in w for w in result.warnings
        )
