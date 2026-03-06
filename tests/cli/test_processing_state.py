"""
Tests for processing state management.

This module tests state management, resume functionality, and state persistence.
"""

import json
from unittest.mock import patch


from transcriptx.cli.processing_state import (
    load_processing_state,
    save_processing_state,
    is_file_processed,
    mark_file_processed,
    get_current_transcript_path_from_state,
)


class TestLoadProcessingState:
    """Tests for load_processing_state function."""

    def test_load_processing_state_existing(self, tmp_path):
        """Test loading existing processing state."""
        state_file = tmp_path / "processing_state.json"
        state_data = {"processed_files": {"file1": {"status": "processed"}}}
        state_file.write_text(json.dumps(state_data))

        with patch(
            "transcriptx.cli.processing_state.PROCESSING_STATE_FILE", state_file
        ):
            state = load_processing_state()

        assert "processed_files" in state
        assert "file1" in state["processed_files"]

    def test_load_processing_state_nonexistent(self, tmp_path):
        """Test loading when state file doesn't exist."""
        state_file = tmp_path / "nonexistent.json"

        with patch(
            "transcriptx.cli.processing_state.PROCESSING_STATE_FILE", state_file
        ):
            state = load_processing_state()

        # Should return default state
        assert isinstance(state, dict)
        assert "processed_files" in state

    def test_load_processing_state_invalid_json(self, tmp_path):
        """Test loading when state file has invalid JSON."""
        state_file = tmp_path / "invalid.json"
        state_file.write_text("invalid json")

        with patch(
            "transcriptx.cli.processing_state.PROCESSING_STATE_FILE", state_file
        ):
            state = load_processing_state()

        # Should return default state on error
        assert isinstance(state, dict)


class TestSaveProcessingState:
    """Tests for save_processing_state function."""

    def test_save_processing_state_success(self, tmp_path):
        """Test saving processing state."""
        state_file = tmp_path / "processing_state.json"
        state_data = {"processed_files": {"file1": {"status": "processed"}}}

        with patch(
            "transcriptx.cli.processing_state.PROCESSING_STATE_FILE", state_file
        ):
            save_processing_state(state_data)

        # Verify file was created
        assert state_file.exists()
        loaded = json.loads(state_file.read_text())
        assert loaded == state_data


class TestIsFileProcessed:
    """Tests for is_file_processed function."""

    def test_is_file_processed_true(self, tmp_path):
        """Test when file is processed."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"wav")

        state = {"processed_files": {str(wav_file): {"status": "processed"}}}

        is_processed = is_file_processed(wav_file, state)

        assert is_processed is True

    def test_is_file_processed_false(self, tmp_path):
        """Test when file is not processed."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"wav")

        state = {"processed_files": {}}

        is_processed = is_file_processed(wav_file, state)

        assert is_processed is False


class TestMarkFileProcessed:
    """Tests for mark_file_processed function."""

    @patch("transcriptx.cli.processing_state.load_processing_state")
    @patch("transcriptx.cli.processing_state.save_processing_state")
    def test_mark_file_processed(self, mock_save, mock_load, tmp_path):
        """Test marking file as processed."""
        wav_file = tmp_path / "test.wav"
        wav_file.write_bytes(b"wav")

        state = {"processed_files": {}}
        mock_load.return_value = state

        mark_file_processed(
            wav_file, {"transcript_path": str(tmp_path / "transcript.json")}
        )

        # Should update state and save
        mock_save.assert_called_once()
        call_args = mock_save.call_args[0][0]
        assert str(wav_file) in call_args["processed_files"]


class TestGetCurrentTranscriptPathFromState:
    """Tests for get_current_transcript_path_from_state function."""

    def test_get_current_transcript_path_found(self, tmp_path):
        """Test getting current transcript path from state."""
        transcript_path = str(tmp_path / "transcript.json")

        state = {
            "processed_files": {
                "wav_file": {
                    "transcript_path": transcript_path,
                    "current_transcript_path": transcript_path,
                }
            }
        }

        with patch(
            "transcriptx.cli.processing_state.load_processing_state", return_value=state
        ):
            result = get_current_transcript_path_from_state(transcript_path)

        assert result == transcript_path

    def test_get_current_transcript_path_not_found(self, tmp_path):
        """Test when transcript path not in state."""
        transcript_path = str(tmp_path / "nonexistent.json")

        state = {"processed_files": {}}

        with patch(
            "transcriptx.cli.processing_state.load_processing_state", return_value=state
        ):
            result = get_current_transcript_path_from_state(transcript_path)

        assert result is None
