"""
Tests for batch resume and checkpoint functionality.

This module tests batch checkpoint creation, retrieval, and resume operations.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from transcriptx.cli.batch_resume import (
    create_batch_checkpoint,
    get_batch_checkpoint,
    clear_batch_checkpoint,
    complete_batch_checkpoint,
    get_remaining_files,
    resume_batch_processing,
)


class TestCreateBatchCheckpoint:
    """Tests for create_batch_checkpoint function."""
    
    def test_creates_checkpoint(self, tmp_path, monkeypatch):
        """Test that checkpoint is created."""
        state_file = tmp_path / "processing_state.json"
        state_file.write_text(json.dumps({}))
        
        with patch('transcriptx.cli.batch_resume.PROCESSING_STATE_FILE', state_file), \
             patch('transcriptx.cli.batch_resume.load_processing_state') as mock_load, \
             patch('transcriptx.cli.batch_resume.save_processing_state') as mock_save:
            
            mock_load.return_value = {}
            
            create_batch_checkpoint(
                batch_id="test_batch",
                total_files=10,
                processed_files=["file1.wav", "file2.wav"],
                failed_files=[],
                current_file="file3.wav"
            )
            
            # Should save state
            mock_save.assert_called_once()
            call_args = mock_save.call_args[0][0]
            assert "batch_progress" in call_args
            assert call_args["batch_progress"]["batch_id"] == "test_batch"
            assert call_args["batch_progress"]["total_files"] == 10
    
    def test_updates_existing_checkpoint(self, tmp_path, monkeypatch):
        """Test that existing checkpoint is updated."""
        state_file = tmp_path / "processing_state.json"
        existing_state = {
            "batch_progress": {
                "batch_id": "test_batch",
                "started_at": "2025-01-01T00:00:00",
                "total_files": 10,
                "processed_files": ["file1.wav"]
            }
        }
        state_file.write_text(json.dumps(existing_state))
        
        with patch('transcriptx.cli.batch_resume.PROCESSING_STATE_FILE', state_file), \
             patch('transcriptx.cli.batch_resume.load_processing_state') as mock_load, \
             patch('transcriptx.cli.batch_resume.save_processing_state') as mock_save:
            
            mock_load.return_value = existing_state
            
            create_batch_checkpoint(
                batch_id="test_batch",
                total_files=10,
                processed_files=["file1.wav", "file2.wav"],
                failed_files=[],
                current_file="file3.wav"
            )
            
            # Should preserve started_at
            call_args = mock_save.call_args[0][0]
            assert call_args["batch_progress"]["started_at"] == "2025-01-01T00:00:00"
            assert len(call_args["batch_progress"]["processed_files"]) == 2


class TestGetBatchCheckpoint:
    """Tests for get_batch_checkpoint function."""
    
    def test_returns_checkpoint_when_exists(self, tmp_path, monkeypatch):
        """Test that checkpoint is returned when it exists."""
        state_file = tmp_path / "processing_state.json"
        checkpoint_data = {
            "batch_id": "test_batch",
            "total_files": 10,
            "processed_files": ["file1.wav"]
        }
        state_data = {"batch_progress": checkpoint_data}
        state_file.write_text(json.dumps(state_data))
        
        with patch('transcriptx.cli.batch_resume.PROCESSING_STATE_FILE', state_file), \
             patch('transcriptx.cli.batch_resume.load_processing_state') as mock_load:
            
            mock_load.return_value = state_data
            
            result = get_batch_checkpoint()
            
            assert result == checkpoint_data
    
    def test_returns_none_when_not_exists(self, tmp_path, monkeypatch):
        """Test that None is returned when checkpoint doesn't exist."""
        state_file = tmp_path / "processing_state.json"
        state_file.write_text(json.dumps({}))
        
        with patch('transcriptx.cli.batch_resume.PROCESSING_STATE_FILE', state_file), \
             patch('transcriptx.cli.batch_resume.load_processing_state') as mock_load:
            
            mock_load.return_value = {}
            
            result = get_batch_checkpoint()
            
            assert result is None


class TestClearBatchCheckpoint:
    """Tests for clear_batch_checkpoint function."""
    
    def test_clears_checkpoint(self, tmp_path, monkeypatch):
        """Test that checkpoint is cleared."""
        state_file = tmp_path / "processing_state.json"
        state_data = {
            "batch_progress": {
                "batch_id": "test_batch",
                "total_files": 10
            }
        }
        state_file.write_text(json.dumps(state_data))
        
        with patch('transcriptx.cli.batch_resume.PROCESSING_STATE_FILE', state_file), \
             patch('transcriptx.cli.batch_resume.load_processing_state') as mock_load, \
             patch('transcriptx.cli.batch_resume.save_processing_state') as mock_save:
            
            mock_load.return_value = state_data.copy()
            
            clear_batch_checkpoint()
            
            # Should save state without batch_progress
            mock_save.assert_called_once()
            call_args = mock_save.call_args[0][0]
            assert "batch_progress" not in call_args


class TestCompleteBatchCheckpoint:
    """Tests for complete_batch_checkpoint function."""
    
    def test_marks_checkpoint_as_completed(self, tmp_path, monkeypatch):
        """Test that checkpoint is marked as completed."""
        state_file = tmp_path / "processing_state.json"
        state_data = {
            "batch_progress": {
                "batch_id": "test_batch",
                "status": "in_progress"
            }
        }
        state_file.write_text(json.dumps(state_data))
        
        with patch('transcriptx.cli.batch_resume.PROCESSING_STATE_FILE', state_file), \
             patch('transcriptx.cli.batch_resume.load_processing_state') as mock_load, \
             patch('transcriptx.cli.batch_resume.save_processing_state') as mock_save:
            
            mock_load.return_value = state_data.copy()
            
            complete_batch_checkpoint()
            
            # Should update status
            mock_save.assert_called_once()
            call_args = mock_save.call_args[0][0]
            assert call_args["batch_progress"]["status"] == "completed"


class TestGetRemainingFiles:
    """Tests for get_remaining_files function."""
    
    def test_returns_unprocessed_files(self, tmp_path):
        """Test that unprocessed files are returned."""
        wav_files = [
            tmp_path / "file1.wav",
            tmp_path / "file2.wav",
            tmp_path / "file3.wav",
        ]
        
        checkpoint = {
            "processed_files": [str(tmp_path / "file1.wav")]
        }
        
        result = get_remaining_files(wav_files, checkpoint)
        
        assert len(result) == 2
        assert tmp_path / "file2.wav" in result
        assert tmp_path / "file3.wav" in result
    
    def test_returns_all_files_when_none_processed(self, tmp_path):
        """Test that all files are returned when none are processed."""
        wav_files = [
            tmp_path / "file1.wav",
            tmp_path / "file2.wav",
        ]
        
        checkpoint = {
            "processed_files": []
        }
        
        result = get_remaining_files(wav_files, checkpoint)
        
        assert len(result) == 2
        assert all(f in result for f in wav_files)
    
    def test_returns_empty_list_when_all_processed(self, tmp_path):
        """Test that empty list is returned when all files are processed."""
        wav_files = [
            tmp_path / "file1.wav",
        ]
        
        checkpoint = {
            "processed_files": [str(tmp_path / "file1.wav")]
        }
        
        result = get_remaining_files(wav_files, checkpoint)
        
        assert len(result) == 0


class TestResumeBatchProcessing:
    """Tests for resume_batch_processing function."""
    
    def test_returns_resume_info_when_checkpoint_exists(self, tmp_path):
        """Test that resume info is returned when checkpoint exists."""
        wav_files = [
            tmp_path / "file1.wav",
            tmp_path / "file2.wav",
        ]
        
        checkpoint = {
            "batch_id": "test_batch",
            "total_files": 2,
            "processed_files": [str(tmp_path / "file1.wav")],
            "failed_files": []
        }
        
        with patch('transcriptx.cli.batch_resume.get_batch_checkpoint') as mock_get:
            mock_get.return_value = checkpoint
            
            result = resume_batch_processing(wav_files)
            
            assert "can_resume" in result
            assert result["can_resume"] is True
            assert "remaining_files" in result
    
    def test_returns_no_resume_when_no_checkpoint(self, tmp_path):
        """Test that no resume info is returned when no checkpoint exists."""
        wav_files = [tmp_path / "file1.wav"]
        
        with patch('transcriptx.cli.batch_resume.get_batch_checkpoint') as mock_get:
            mock_get.return_value = None
            
            result = resume_batch_processing(wav_files)
            
            assert result["can_resume"] is False
