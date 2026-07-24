"""
Tests for transcript loading operations.

Runtime ``load_segments`` accepts only schema v1.0 artifacts; raw / legacy JSON
must use the import pipeline first.
"""

import json
from unittest.mock import patch

import pytest

from transcriptx.io import load_transcript_data
from transcriptx.io.transcript_loader import (
    load_canonical_transcript,
    load_segments,
    load_transcript,
)


def _v1_source(path: str = "test.json") -> dict:
    return {
        "type": "manual",
        "original_path": path,
        "imported_at": "2020-01-01T00:00:00+00:00",
    }


def _v1_doc(segments: list, *, source_path: str = "test.json") -> dict:
    return {
        "schema_version": 1,
        "source": _v1_source(source_path),
        "segments": segments,
    }


class TestLoadSegments:
    """Tests for load_segments function (v1.0 artifacts only)."""

    def test_loads_segments_from_v1_file(self, tmp_path):
        test_file = tmp_path / "test.json"
        data = _v1_doc(
            [
                {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
                {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
            ]
        )
        test_file.write_text(json.dumps(data))

        segments = load_segments(str(test_file))

        assert len(segments) == 2
        assert segments[0]["speaker"] == "SPEAKER_00"
        assert segments[1]["speaker"] == "SPEAKER_01"

    def test_rejects_bare_segment_list_file(self, tmp_path):
        test_file = tmp_path / "test.json"
        data = [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
        ]
        test_file.write_text(json.dumps(data))

        with pytest.raises(ValueError, match="schema v1.0"):
            load_segments(str(test_file))

    def test_rejects_dict_without_schema_version(self, tmp_path):
        test_file = tmp_path / "test.json"
        data = {
            "segments": [
                {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            ]
        }
        test_file.write_text(json.dumps(data))

        with pytest.raises(ValueError, match="schema_version|schema v1.0"):
            load_segments(str(test_file))

    def test_rejects_raw_whisperx_shape_without_v1_wrapper(self, tmp_path):
        test_file = tmp_path / "test.json"
        data = {
            "segments": [
                {
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 2.0,
                    "words": [
                        {
                            "word": "Hello",
                            "speaker": "SPEAKER_00",
                            "start": 0.0,
                            "end": 1.0,
                        },
                    ],
                }
            ]
        }
        test_file.write_text(json.dumps(data))

        with pytest.raises(ValueError, match="schema_version|schema v1.0"):
            load_segments(str(test_file))

    def test_accepts_v1_with_words_and_segment_speaker(self, tmp_path):
        test_file = tmp_path / "test.json"
        data = _v1_doc(
            [
                {
                    "speaker": "SPEAKER_00",
                    "text": "Hello world",
                    "start": 0.0,
                    "end": 2.0,
                    "words": [
                        {
                            "word": "Hello",
                            "speaker": "SPEAKER_00",
                            "start": 0.0,
                            "end": 1.0,
                        },
                    ],
                }
            ]
        )
        test_file.write_text(json.dumps(data))

        segments = load_segments(str(test_file))
        assert len(segments) == 1
        assert segments[0]["speaker"] == "SPEAKER_00"

    def test_empty_segments_allowed_with_warning(self, tmp_path):
        test_file = tmp_path / "test.json"
        data = _v1_doc([])
        test_file.write_text(json.dumps(data))

        segments = load_segments(str(test_file))
        assert segments == []

    def test_raises_error_on_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_segments("/nonexistent/file.json")

    def test_filenotfound_includes_original_path(self):
        with pytest.raises(
            FileNotFoundError, match="Transcript file not found: /nonexistent/file.json"
        ):
            load_segments("/nonexistent/file.json")

    def test_handles_invalid_json(self, tmp_path):
        test_file = tmp_path / "test.json"
        test_file.write_text("invalid json content")

        with pytest.raises(json.JSONDecodeError):
            load_segments(str(test_file))

    def test_load_segments_with_data_v1(self, tmp_path):
        test_file = tmp_path / "test.json"
        data = _v1_doc(
            [
                {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
                {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
            ]
        )
        test_file.write_text(json.dumps(data))

        from_file = load_segments(str(test_file))
        from_data = load_segments(str(test_file), data=data)

        assert from_data == from_file

    def test_load_segments_data_rejects_non_v1(self, tmp_path):
        test_file = tmp_path / "test.json"
        bad = {"segments": [{"speaker": "A", "text": "x", "start": 0.0, "end": 1.0}]}
        with pytest.raises(ValueError, match="schema_version|schema v1.0"):
            load_segments(str(test_file), data=bad)

    def test_rejects_non_json_suffix(self, tmp_path):
        path = tmp_path / "note.txt"
        path.write_text("not json")
        with pytest.raises(ValueError, match=r"only accepts \.json"):
            load_segments(str(path))

    def test_rejects_segments_not_list(self, tmp_path):
        data = _v1_doc([])
        data["segments"] = {"speaker": "A", "text": "x"}
        with pytest.raises(ValueError, match="segments' must be a list"):
            load_segments(str(tmp_path / "x.json"), data=data)

    def test_resolves_missing_path_via_path_resolution(self, tmp_path):
        real = tmp_path / "resolved.json"
        real.write_text(
            json.dumps(
                _v1_doc(
                    [
                        {
                            "speaker": "SPEAKER_00",
                            "text": "Hello",
                            "start": 0.0,
                            "end": 1.0,
                        }
                    ]
                )
            )
        )
        missing = str(tmp_path / "missing.json")
        with patch(
            "transcriptx.core.utils._path_resolution.resolve_file_path",
            return_value=str(real),
        ):
            segments = load_segments(missing)
        assert len(segments) == 1
        assert segments[0]["speaker"] == "SPEAKER_00"


class TestLoadCanonicalTranscript:
    """Tests for load_canonical_transcript."""

    def test_builds_canonical_from_v1_file(self, tmp_path):
        path = tmp_path / "canon.json"
        path.write_text(
            json.dumps(
                _v1_doc(
                    [
                        {
                            "speaker": "SPEAKER_00",
                            "text": "Hello",
                            "start": 0.0,
                            "end": 1.0,
                        }
                    ]
                )
            )
        )
        canon = load_canonical_transcript(str(path))
        assert len(canon.segments) == 1
        assert canon.segments[0]["speaker"] == "SPEAKER_00"

    def test_empty_segments_raises(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text(json.dumps(_v1_doc([])))
        with pytest.raises(ValueError, match="No segments found"):
            load_canonical_transcript(str(path))


class TestLoadTranscript:
    """Tests for load_transcript function."""

    def test_loads_complete_transcript(self, tmp_path):
        test_file = tmp_path / "test.json"
        data = {
            "schema_version": 1,
            "source": _v1_source(),
            "segments": [
                {"speaker": "SPEAKER_00", "text": "Hello", "start": 0, "end": 1}
            ],
            "metadata": {"version": "1.0"},
        }
        test_file.write_text(json.dumps(data))

        loaded = load_transcript(str(test_file))

        assert loaded == data
        assert "segments" in loaded

    def test_preserves_all_fields(self, tmp_path):
        test_file = tmp_path / "test.json"
        data = {
            "schema_version": 1,
            "source": _v1_source(),
            "segments": [
                {"speaker": "SPEAKER_00", "text": "Hello", "start": 0, "end": 1}
            ],
            "custom_field": "custom_value",
            "nested": {"key": "value"},
        }
        test_file.write_text(json.dumps(data))

        loaded = load_transcript(str(test_file))

        assert loaded == data
        assert loaded["custom_field"] == "custom_value"

    def test_raises_error_on_nonexistent_file(self):
        with pytest.raises(FileNotFoundError):
            load_transcript("/nonexistent/file.json")

    def test_handles_invalid_json(self, tmp_path):
        test_file = tmp_path / "test.json"
        test_file.write_text("invalid json content")

        with pytest.raises(json.JSONDecodeError):
            load_transcript(str(test_file))

    def test_rejects_non_json_suffix(self, tmp_path):
        path = tmp_path / "clip.vtt"
        path.write_text("WEBVTT\n")
        with pytest.raises(ValueError, match="only handles JSON"):
            load_transcript(str(path))

    def test_json_decode_error_includes_near_position_snippet(self, tmp_path):
        path = tmp_path / "broken.json"
        # Valid prefix then a clear breakage so pos is past the start.
        path.write_text('{"ok": true, "bad": }')
        with pytest.raises(json.JSONDecodeError, match="Near position") as exc_info:
            load_transcript(str(path))
        assert "line" in str(exc_info.value).lower() or "Near position" in str(
            exc_info.value
        )

    def test_resolves_missing_path_via_path_resolution(self, tmp_path):
        real = tmp_path / "resolved.json"
        payload = {"schema_version": 1, "source": _v1_source(), "segments": []}
        real.write_text(json.dumps(payload))
        missing = str(tmp_path / "gone.json")
        with patch(
            "transcriptx.core.utils._path_resolution.resolve_file_path",
            return_value=str(real),
        ):
            loaded = load_transcript(missing)
        assert loaded == payload


class TestLoadTranscriptData:
    """Tests for load_transcript_data (io package wrapper)."""

    def test_loads_complete_data(self, tmp_path):
        test_file = tmp_path / "test.json"
        segs = [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
        ]
        test_file.write_text(json.dumps(_v1_doc(segs)))

        with patch("transcriptx.io.get_transcript_service") as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.load_transcript_data.return_value = (
                segs,
                "test",
                str(tmp_path),
            )

            segments, base_name, transcript_dir = load_transcript_data(str(test_file))

            assert len(segments) == 1
            assert base_name == "test"
            assert transcript_dir == str(tmp_path)

    def test_raises_error_on_nonexistent_file(self):
        with patch("transcriptx.io.get_transcript_service") as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.load_transcript_data.side_effect = FileNotFoundError(
                "Transcript file not found"
            )

            with pytest.raises(FileNotFoundError):
                load_transcript_data("/nonexistent/file.json")

    def test_raises_error_on_empty_segments(self, tmp_path):
        test_file = tmp_path / "test.json"
        test_file.write_text(json.dumps(_v1_doc([])))

        with patch("transcriptx.io.get_transcript_service") as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.load_transcript_data.side_effect = ValueError(
                "No segments found"
            )

            with pytest.raises(ValueError):
                load_transcript_data(str(test_file))

    def test_passes_batch_mode_flag(self, tmp_path):
        test_file = tmp_path / "test.json"
        test_file.write_text(
            json.dumps(
                _v1_doc(
                    [
                        {
                            "speaker": "SPEAKER_00",
                            "text": "Hello",
                            "start": 0.0,
                            "end": 1.0,
                        }
                    ]
                )
            )
        )

        with patch("transcriptx.io.get_transcript_service") as mock_service:
            mock_service_instance = mock_service.return_value
            mock_service_instance.load_transcript_data.return_value = (
                [{"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0}],
                "test",
                str(tmp_path),
            )

            load_transcript_data(str(test_file), batch_mode=True)

            call_args = mock_service_instance.load_transcript_data.call_args
            assert call_args.kwargs.get("batch_mode") is True
