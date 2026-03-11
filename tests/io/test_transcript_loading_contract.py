"""
Phase 0 safety net: contract tests for canonical transcript loading behavior.

Locks the behavior of TranscriptService.load_segments, transcript_loader.load_segments,
TranscriptService.load_transcript_data, and path-resolution so refactors (e.g. unification)
do not silently change semantics.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.io.transcript_loader import load_segments, load_transcript_data
from transcriptx.io.transcript_service import (
    TranscriptService,
    get_transcript_service,
    reset_transcript_service,
)


def _fixture_transcript(tmp_path: Path) -> tuple[str, list, dict]:
    """Create a fixture JSON and return (path, segments, full_data)."""
    data = {
        "segments": [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
        ],
        "speaker_map": {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"},
    }
    path = tmp_path / "meeting.json"
    path.write_text(json.dumps(data))
    return str(path), data["segments"], data


class TestCanonicalTranscriptLoadingContract:
    """Canonical behavior: loader and service agree on segment count and key fields."""

    def test_load_segments_loader_and_service_same_count_and_keys(
        self, tmp_path: Path
    ) -> None:
        """Given a fixture JSON path, load_segments (loader) and TranscriptService.load_segments return same segment count and key fields."""
        path, expected_segments, _ = _fixture_transcript(tmp_path)
        reset_transcript_service()
        try:
            from transcriptx.io.transcript_loader import (
                load_segments as loader_load_segments,
            )

            loader_segments = loader_load_segments(path)
            service = get_transcript_service()
            service_segments = service.load_segments(path)

            assert (
                len(loader_segments) == len(service_segments) == len(expected_segments)
            )
            for i, (ls, ss) in enumerate(zip(loader_segments, service_segments)):
                assert ls.get("speaker") == ss.get("speaker")
                assert ls.get("text") == ss.get("text")
                assert "start" in ls and "start" in ss
                assert "end" in ls and "end" in ss
        finally:
            reset_transcript_service()

    def test_load_transcript_data_returns_expected_tuple_shape(
        self, tmp_path: Path
    ) -> None:
        """TranscriptService.load_transcript_data returns (segments, base_name, transcript_dir, speaker_map)."""
        path, expected_segments, _ = _fixture_transcript(tmp_path)
        reset_transcript_service()
        try:
            with (
                patch(
                    "transcriptx.io.transcript_service.get_canonical_base_name"
                ) as mock_base,
                patch(
                    "transcriptx.io.transcript_service.get_transcript_dir"
                ) as mock_dir,
            ):
                mock_base.return_value = "meeting"
                mock_dir.return_value = str(tmp_path)

                service = get_transcript_service()
                result = service.load_transcript_data(path)

            assert isinstance(result, tuple)
            assert len(result) == 4
            segments, base_name, transcript_dir, speaker_map = result
            assert isinstance(segments, list)
            assert len(segments) == len(expected_segments)
            assert base_name == "meeting"
            assert transcript_dir == str(tmp_path)
            assert isinstance(speaker_map, dict)
        finally:
            reset_transcript_service()

    def test_load_transcript_data_tuple_unpacking_still_works(
        self, tmp_path: Path
    ) -> None:
        """load_transcript_data (via loader) returns tuple that can be unpacked as segments, base_name, transcript_dir, speaker_map."""
        path, _, _ = _fixture_transcript(tmp_path)
        stub = (
            [{"speaker": "S1", "text": "Hi"}],
            "meeting",
            str(tmp_path),
            {"S1": "Alice"},
        )
        with patch(
            "transcriptx.io.transcript_service.get_transcript_service"
        ) as mock_get:
            service = TranscriptService()
            service.load_transcript_data = lambda *a, **k: stub
            mock_get.return_value = service

            segments, base_name, transcript_dir, speaker_map = load_transcript_data(
                path
            )
            assert len(segments) == 1
            assert base_name == "meeting"
            assert transcript_dir == str(tmp_path)
            assert speaker_map == {"S1": "Alice"}


class TestPathResolutionContract:
    """Path-resolution edge case: renamed transcript (original path missing, resolution finds file)."""

    def test_load_segments_uses_resolution_when_path_missing(
        self, tmp_path: Path
    ) -> None:
        """When path does not exist, load_segments uses resolve_file_path; if resolution returns existing file, segments from that file are returned."""
        resolved_file = tmp_path / "resolved.json"
        data = {
            "segments": [
                {"speaker": "SPEAKER_00", "text": "Resolved", "start": 0.0, "end": 1.0},
            ]
        }
        resolved_file.write_text(json.dumps(data))

        original_path = str(tmp_path / "missing_renamed.json")
        assert not Path(original_path).exists()

        with patch(
            "transcriptx.core.utils._path_resolution.resolve_file_path",
            return_value=str(resolved_file),
        ):
            segments = load_segments(original_path)

        assert len(segments) == 1
        assert segments[0].get("text") == "Resolved"

    def test_load_segments_raises_file_not_found_with_original_path_when_resolution_fails(
        self,
    ) -> None:
        """When path does not exist and resolution fails, FileNotFoundError mentions the original path."""
        original_path = "/nonexistent/original_transcript.json"
        with patch(
            "transcriptx.core.utils._path_resolution.resolve_file_path",
            side_effect=FileNotFoundError("not found"),
        ):
            with pytest.raises(FileNotFoundError) as exc_info:
                load_segments(original_path)
            assert original_path in str(exc_info.value)


class TestTranscriptServiceLoadTranscriptDataContract:
    """transcript_loader.load_transcript_data(path) returns TranscriptLoadResult with segments."""

    def test_service_load_transcript_data_returns_dict_with_segments(
        self, tmp_path: Path
    ) -> None:
        from transcriptx.io.transcript_loader import load_transcript_data

        path, segments, _ = _fixture_transcript(tmp_path)
        result = load_transcript_data(path)
        assert hasattr(result, "segments")
        assert len(result.segments) == len(segments)
