"""
Tests for file I/O operations.

This module tests JSON/CSV/transcript saving, directory validation,
and error handling for file operations.
"""

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from transcriptx.io.file_io import (
    save_json,
    save_csv,
    save_transcript,
    write_transcript_files,
    _validate_directory_creation,
)


class TestValidateDirectoryCreation:
    """Tests for directory validation function."""

    def test_allows_valid_paths(self, tmp_path):
        """Test that valid paths are allowed."""
        test_file = tmp_path / "test.json"
        assert _validate_directory_creation(str(test_file)) is True

    def test_allows_readable_subdirectory(self, tmp_path, monkeypatch):
        """Test that 'readable' subdirectory in transcripts folder is allowed."""
        # Mock DIARISED_TRANSCRIPTS_DIR to point to tmp_path
        from transcriptx.io import file_io

        monkeypatch.setattr(file_io, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path))

        readable_dir = tmp_path / "readable"
        test_file = readable_dir / "test.json"
        assert _validate_directory_creation(str(test_file)) is True

    def test_blocks_invalid_subdirectory(self, tmp_path, monkeypatch):
        """Test that invalid subdirectories in transcripts folder are blocked."""
        # Mock DIARISED_TRANSCRIPTS_DIR to point to tmp_path
        from transcriptx.io import file_io

        monkeypatch.setattr(file_io, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path))

        invalid_dir = tmp_path / "raw"
        test_file = invalid_dir / "test.json"
        assert _validate_directory_creation(str(test_file)) is False

    def test_allows_transcripts_directory_itself(self, tmp_path, monkeypatch):
        """Test that transcripts directory itself is allowed."""
        from transcriptx.io import file_io

        monkeypatch.setattr(file_io, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path))

        test_file = tmp_path / "test.json"
        assert _validate_directory_creation(str(test_file)) is True

    def test_handles_path_resolution_errors(self):
        """Test that path resolution errors are handled gracefully."""
        # Invalid path that might cause resolution issues
        invalid_path = "/nonexistent/../../invalid"
        # Should return True (allow) if resolution fails
        result = _validate_directory_creation(invalid_path)
        assert isinstance(result, bool)


class TestSaveJson:
    """Tests for save_json function."""

    def test_saves_simple_dict(self, tmp_path):
        """Test saving a simple dictionary."""
        test_file = tmp_path / "test.json"
        data = {"key": "value", "number": 42}

        save_json(data, str(test_file))

        assert test_file.exists()
        with open(test_file) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_saves_nested_dict(self, tmp_path):
        """Test saving nested dictionaries."""
        test_file = tmp_path / "test.json"
        data = {"outer": {"inner": "value", "list": [1, 2, 3]}}

        save_json(data, str(test_file))

        with open(test_file) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_handles_numpy_integers(self, tmp_path):
        """Test that numpy integers are converted to Python ints."""
        test_file = tmp_path / "test.json"
        data = {"int": np.int64(42), "float": np.float64(3.14)}

        save_json(data, str(test_file))

        with open(test_file) as f:
            loaded = json.load(f)
        assert isinstance(loaded["int"], int)
        assert isinstance(loaded["float"], float)
        assert loaded["int"] == 42
        assert loaded["float"] == 3.14

    def test_handles_numpy_arrays(self, tmp_path):
        """Test that numpy arrays are converted to lists."""
        test_file = tmp_path / "test.json"
        data = {"array": np.array([1, 2, 3])}

        save_json(data, str(test_file))

        with open(test_file) as f:
            loaded = json.load(f)
        assert isinstance(loaded["array"], list)
        assert loaded["array"] == [1, 2, 3]

    def test_creates_directory_if_needed(self, tmp_path):
        """Test that parent directory is created if it doesn't exist."""
        test_file = tmp_path / "subdir" / "test.json"
        data = {"key": "value"}

        save_json(data, str(test_file))

        assert test_file.exists()
        assert test_file.parent.exists()

    def test_raises_error_on_invalid_subdirectory(self, tmp_path, monkeypatch):
        """Test that invalid subdirectory creation raises error."""
        from transcriptx.io import file_io

        monkeypatch.setattr(file_io, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path))

        invalid_file = tmp_path / "raw" / "test.json"
        data = {"key": "value"}

        with pytest.raises(ValueError, match="Invalid subdirectory"):
            save_json(data, str(invalid_file))

    def test_handles_unicode(self, tmp_path):
        """Test that unicode characters are saved correctly."""
        test_file = tmp_path / "test.json"
        data = {"text": "Hello 世界 🌍", "emoji": "🎤"}

        save_json(data, str(test_file))

        with open(test_file, encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["text"] == "Hello 世界 🌍"
        assert loaded["emoji"] == "🎤"


class TestSaveCsv:
    """Tests for save_csv function."""

    def test_saves_simple_rows(self, tmp_path):
        """Test saving simple rows."""
        test_file = tmp_path / "test.csv"
        rows = [["Alice", "30"], ["Bob", "25"]]

        save_csv(rows, str(test_file))

        assert test_file.exists()
        with open(test_file, newline="") as f:
            reader = csv.reader(f)
            loaded = list(reader)
        assert loaded == rows

    def test_saves_with_header(self, tmp_path):
        """Test saving with header row."""
        test_file = tmp_path / "test.csv"
        rows = [["Alice", "30"], ["Bob", "25"]]
        header = ["Name", "Age"]

        save_csv(rows, str(test_file), header=header)

        with open(test_file, newline="") as f:
            reader = csv.reader(f)
            loaded = list(reader)
        assert loaded[0] == header
        assert loaded[1:] == rows

    def test_creates_directory_if_needed(self, tmp_path):
        """Test that parent directory is created if it doesn't exist."""
        test_file = tmp_path / "subdir" / "test.csv"
        rows = [["Alice", "30"]]

        save_csv(rows, str(test_file))

        assert test_file.exists()
        assert test_file.parent.exists()

    def test_raises_error_on_invalid_subdirectory(self, tmp_path, monkeypatch):
        """Test that invalid subdirectory creation raises error."""
        from transcriptx.io import file_io

        monkeypatch.setattr(file_io, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path))

        invalid_file = tmp_path / "raw" / "test.csv"
        rows = [["Alice", "30"]]

        with pytest.raises(ValueError, match="Invalid subdirectory"):
            save_csv(rows, str(invalid_file))

    def test_handles_empty_rows(self, tmp_path):
        """Test saving empty rows."""
        test_file = tmp_path / "test.csv"
        rows = []
        header = ["Name", "Age"]

        save_csv(rows, str(test_file), header=header)

        with open(test_file, newline="") as f:
            reader = csv.reader(f)
            loaded = list(reader)
        assert loaded == [header]


class TestSaveTranscript:
    """Tests for save_transcript function."""

    def test_saves_list_of_segments(self, tmp_path):
        """Test saving list of segments."""
        test_file = tmp_path / "test.json"
        segments = [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
        ]

        save_transcript(segments, str(test_file))

        assert test_file.exists()
        with open(test_file) as f:
            loaded = json.load(f)
        assert "segments" in loaded
        assert loaded["segments"] == segments

    def test_saves_dict_directly(self, tmp_path):
        """Test saving dict directly (not wrapped in segments)."""
        test_file = tmp_path / "test.json"
        data = {"segments": [{"text": "Hello"}], "metadata": {"version": "1.0"}}

        save_transcript(data, str(test_file))

        with open(test_file) as f:
            loaded = json.load(f)
        assert loaded == data

    def test_creates_directory_if_needed(self, tmp_path):
        """Test that parent directory is created if it doesn't exist."""
        test_file = tmp_path / "subdir" / "test.json"
        segments = [{"speaker": "SPEAKER_00", "text": "Hello"}]

        save_transcript(segments, str(test_file))

        assert test_file.exists()
        assert test_file.parent.exists()

    def test_raises_error_on_invalid_subdirectory(self, tmp_path, monkeypatch):
        """Test that invalid subdirectory creation raises error."""
        from transcriptx.io import file_io

        monkeypatch.setattr(file_io, "DIARISED_TRANSCRIPTS_DIR", str(tmp_path))

        invalid_file = tmp_path / "raw" / "test.json"
        segments = [{"speaker": "SPEAKER_00", "text": "Hello"}]

        with pytest.raises(ValueError, match="Invalid subdirectory"):
            save_transcript(segments, str(invalid_file))


class TestWriteTranscriptFiles:
    """Tests for write_transcript_files function."""

    def test_writes_txt_and_csv_files(self, tmp_path):
        """Test that both TXT and CSV files are created."""
        segments = [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_00", "text": "World", "start": 1.0, "end": 2.0},
        ]
        speaker_map = {"SPEAKER_00": "Alice"}
        base_name = "test"
        out_dir = str(tmp_path)

        def format_time(seconds):
            return f"{int(seconds)}s"

        txt_path, csv_path = write_transcript_files(
            segments, speaker_map, base_name, out_dir, format_time
        )

        assert Path(txt_path).exists()
        assert Path(csv_path).exists()
        assert "test-transcript.txt" in txt_path
        assert "test-transcript.csv" in csv_path

    def test_csv_has_correct_format(self, tmp_path):
        """Test that CSV file has correct format."""
        segments = [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_01", "text": "World", "start": 1.0, "end": 2.0},
        ]
        speaker_map = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
        base_name = "test"
        out_dir = str(tmp_path)

        def format_time(seconds):
            return f"{int(seconds)}s"

        txt_path, csv_path = write_transcript_files(
            segments, speaker_map, base_name, out_dir, format_time
        )

        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        assert rows[0] == ["Speaker", "Timestamp", "Text"]
        assert rows[1] == ["Alice", "0s", "Hello"]
        assert rows[2] == ["Bob", "1s", "World"]

    def test_handles_speaker_changes(self, tmp_path):
        """Test that speaker changes are handled correctly in TXT."""
        segments = [
            {"speaker": "SPEAKER_00", "text": "First", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_01", "text": "Second", "start": 1.0, "end": 2.0},
        ]
        speaker_map = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
        base_name = "test"
        out_dir = str(tmp_path)

        def format_time(seconds):
            return f"{int(seconds)}s"

        txt_path, csv_path = write_transcript_files(
            segments, speaker_map, base_name, out_dir, format_time
        )

        with open(txt_path) as f:
            content = f.read()

        assert "Alice" in content
        assert "Bob" in content
        assert "First" in content
        assert "Second" in content

    def test_handles_pauses(self, tmp_path):
        """Test that pauses are included in TXT output."""
        segments = [
            {
                "speaker": "SPEAKER_00",
                "text": "Hello",
                "start": 0.0,
                "end": 1.0,
                "pause": 3.0,
            },
        ]
        speaker_map = {"SPEAKER_00": "Alice"}
        base_name = "test"
        out_dir = str(tmp_path)

        def format_time(seconds):
            return f"{int(seconds)}s"

        txt_path, csv_path = write_transcript_files(
            segments, speaker_map, base_name, out_dir, format_time
        )

        with open(txt_path) as f:
            content = f.read()

        assert "pause" in content.lower() or "⏸️" in content

    def test_handles_missing_speaker_in_map(self, tmp_path):
        """Test that missing speakers in map use speaker ID."""
        segments = [
            {"speaker": "SPEAKER_00", "text": "Hello", "start": 0.0, "end": 1.0},
            {"speaker": "SPEAKER_99", "text": "World", "start": 1.0, "end": 2.0},
        ]
        speaker_map = {"SPEAKER_00": "Alice"}  # Missing SPEAKER_99
        base_name = "test"
        out_dir = str(tmp_path)

        def format_time(seconds):
            return f"{int(seconds)}s"

        txt_path, csv_path = write_transcript_files(
            segments, speaker_map, base_name, out_dir, format_time
        )

        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # Should use speaker ID for missing speaker
        assert rows[2][0] == "SPEAKER_99"
