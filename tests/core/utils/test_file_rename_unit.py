"""Unit tests for file_rename helpers (date extraction, UUID heuristics, audio lookup)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from transcriptx.core.utils.file_rename import (
    _looks_like_uuid,
    extract_date_prefix,
    extract_date_prefix_from_filename,
    extract_date_prefix_from_transcript,
    find_original_audio_file,
)


class TestLooksLikeUUID:
    """Tests for the _looks_like_uuid helper."""

    def test_valid_uuid_strings_return_true(self) -> None:
        assert _looks_like_uuid("550e8400-e29b-41d4-a716-446655440000") is True
        assert _looks_like_uuid("00000000-0000-0000-0000-000000000000") is True

    def test_invalid_keys_return_false(self) -> None:
        assert _looks_like_uuid("") is False
        assert _looks_like_uuid("not-a-uuid") is False
        assert _looks_like_uuid("550e8400-e29b-41d4-a716") is False
        assert _looks_like_uuid("550e8400e29b41d4a716446655440000") is False


class TestExtractDatePrefixFromFilename:
    """Tests for extract_date_prefix_from_filename."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("20251230160235.wav", "251230_"),  # YYYYMMDDHHMMSS
            ("20240101120000.m4a", "240101_"),
            ("251230_recording.wav", "251230_"),  # YYMMDD prefix
            ("000101_test.wav", "000101_"),  # Y2K edge
            ("invalid.wav", ""),
            ("20251301120000.wav", ""),  # invalid month
        ],
    )
    def test_patterns(self, name: str, expected: str) -> None:
        assert extract_date_prefix_from_filename(name) == expected


class TestExtractDatePrefixFromFilesystem:
    """Tests for extract_date_prefix / extract_date_prefix_from_transcript using mtimes."""

    def test_extract_date_prefix_uses_filename_when_available(
        self, tmp_path: Path
    ) -> None:
        p = tmp_path / "20250102123456.wav"
        p.write_bytes(b"data")
        # mtime would produce a different value, but filename wins
        assert extract_date_prefix(p) == "250102_"

    def test_extract_date_prefix_falls_back_to_mtime(self, tmp_path: Path) -> None:
        p = tmp_path / "audio.wav"
        p.write_bytes(b"data")
        dt = datetime(2025, 1, 2, 3, 4, 5)
        ts = dt.timestamp()
        # Set both atime and mtime
        pytest.importorskip("os").utime(p, (ts, ts))

        prefix = extract_date_prefix(p)
        assert prefix.startswith("25")  # year prefix
        # Ensure it is exactly YYMMDD_
        assert len(prefix) == 7 and prefix.endswith("_")

    def test_extract_date_prefix_logs_and_returns_empty_for_missing_file(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "missing.wav"
        assert extract_date_prefix(missing) == ""

    def test_extract_date_prefix_from_transcript_uses_filename_first(
        self, tmp_path: Path
    ) -> None:
        t = tmp_path / "251231_transcript.json"
        t.write_text("{}", encoding="utf-8")
        assert extract_date_prefix_from_transcript(t) == "251231_"

    def test_extract_date_prefix_from_transcript_falls_back_to_mtime(
        self, tmp_path: Path
    ) -> None:
        t = tmp_path / "no_date.json"
        t.write_text("{}", encoding="utf-8")
        dt = datetime(2024, 2, 3, 4, 5, 6)
        ts = dt.timestamp()
        pytest.importorskip("os").utime(t, (ts, ts))

        prefix = extract_date_prefix_from_transcript(t)
        assert prefix == "240203_"

    def test_extract_date_prefix_from_transcript_missing_file_returns_empty(
        self, tmp_path: Path
    ) -> None:
        missing = tmp_path / "missing.json"
        assert extract_date_prefix_from_transcript(missing) == ""


class TestFindOriginalAudioFile:
    """Tests for find_original_audio_file using synthetic processing_state payloads."""

    def _write_state(self, state_path: Path, payload: dict) -> None:
        state_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_prefers_audio_path_from_state_metadata(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        transcript = tmp_path / "t.json"
        transcript.write_text("{}", encoding="utf-8")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"x")

        state_file = tmp_path / "processing_state.json"
        self._write_state(
            state_file,
            {
                "processed_files": {
                    "uuid-1": {
                        "transcript_path": str(transcript),
                        "audio_path": str(audio),
                    }
                }
            },
        )

        monkeypatch.setattr(
            "transcriptx.core.utils.file_rename.PROCESSING_STATE_FILE", state_file
        )

        result = find_original_audio_file(str(transcript))
        assert result == audio

    def test_uses_legacy_key_as_audio_path_when_not_uuid(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        transcript = tmp_path / "t.json"
        transcript.write_text("{}", encoding="utf-8")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"x")

        state_file = tmp_path / "processing_state.json"
        # key is the audio path (pre-UUID format)
        self._write_state(
            state_file,
            {
                "processed_files": {
                    str(audio): {
                        "transcript_path": str(transcript),
                    }
                }
            },
        )

        monkeypatch.setattr(
            "transcriptx.core.utils.file_rename.PROCESSING_STATE_FILE", state_file
        )

        result = find_original_audio_file(str(transcript))
        assert result == audio

    def test_uses_mp3_path_in_metadata_when_present(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        transcript = tmp_path / "t.json"
        transcript.write_text("{}", encoding="utf-8")
        audio = tmp_path / "audio.mp3"
        audio.write_bytes(b"x")

        state_file = tmp_path / "processing_state.json"
        self._write_state(
            state_file,
            {
                "processed_files": {
                    "uuid-1": {
                        "transcript_path": str(transcript),
                        "mp3_path": str(audio),
                    }
                }
            },
        )

        monkeypatch.setattr(
            "transcriptx.core.utils.file_rename.PROCESSING_STATE_FILE", state_file
        )

        result = find_original_audio_file(str(transcript))
        assert result == audio

    def test_returns_none_when_no_candidates_exist(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        transcript = tmp_path / "t.json"
        transcript.write_text("{}", encoding="utf-8")

        state_file = tmp_path / "processing_state.json"
        self._write_state(state_file, {"processed_files": {}})
        monkeypatch.setattr(
            "transcriptx.core.utils.file_rename.PROCESSING_STATE_FILE", state_file
        )

        # Also ensure recordings dirs are empty
        monkeypatch.setattr(
            "transcriptx.core.utils.file_rename.RECORDINGS_DIR", tmp_path / "recordings"
        )
        monkeypatch.setattr(
            "transcriptx.core.utils.file_rename.OUTPUTS_DIR", tmp_path / "outputs"
        )

        result = find_original_audio_file(str(transcript))
        assert result is None

    def test_finds_audio_by_stripped_copy_suffix_when_transcript_renamed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Transcript `base (1).json` should still match `base.wav` in recordings."""
        recordings = tmp_path / "recordings"
        recordings.mkdir(parents=True, exist_ok=True)
        audio = recordings / "250612_CSE2.wav"
        audio.write_bytes(b"x")

        transcript = tmp_path / "250612_CSE2 (1).json"
        transcript.write_text("{}", encoding="utf-8")

        state_file = tmp_path / "processing_state.json"
        state_file.write_text(json.dumps({"processed_files": {}}), encoding="utf-8")

        monkeypatch.setattr(
            "transcriptx.core.utils.file_rename.PROCESSING_STATE_FILE", state_file
        )
        monkeypatch.setattr(
            "transcriptx.core.utils.file_rename.RECORDINGS_DIR", recordings
        )
        monkeypatch.setattr(
            "transcriptx.core.utils.file_rename.OUTPUTS_DIR", tmp_path / "outputs"
        )

        result = find_original_audio_file(str(transcript))
        assert result == audio
