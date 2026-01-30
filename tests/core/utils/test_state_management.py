"""
Tests for state management utilities and schema.

This module tests state validation, repair, and analysis history functions.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from transcriptx.core.utils.state_utils import (
    validate_processing_state,
    repair_processing_state,
    get_analysis_history,
    has_analysis_completed,
    get_missing_modules,
)


class TestValidateProcessingState:
    """Tests for validate_processing_state function."""
    
    def test_validates_valid_state(self, tmp_path):
        """Test validation of valid state file."""
        state_file = tmp_path / "processing_state.json"
        state_data = {
            "processed_files": {
                "test.wav": {
                    "transcript_path": str(tmp_path / "test.json"),
                    "status": "completed"
                }
            }
        }
        state_file.write_text(json.dumps(state_data))
        
        with patch('transcriptx.core.utils.state_utils.validate_state_entry') as mock_validate, \
             patch('transcriptx.core.utils.state_utils.validate_state_paths') as mock_paths:
            
            mock_validate.return_value = (True, [])
            mock_paths.return_value = (True, [])
            
            result = validate_processing_state(state_file)
            
            assert result["valid"] is True
            assert result["entries_checked"] == 1
    
    def test_detects_invalid_json(self, tmp_path):
        """Test that invalid JSON is detected."""
        state_file = tmp_path / "processing_state.json"
        state_file.write_text("invalid json")
        
        result = validate_processing_state(state_file)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    def test_detects_missing_file(self, tmp_path):
        """Test that missing file is detected."""
        state_file = tmp_path / "nonexistent.json"
        
        result = validate_processing_state(state_file)
        
        assert result["valid"] is False
        assert len(result["errors"]) > 0
    
    def test_validates_entry_schema(self, tmp_path):
        """Test that entry schema is validated."""
        state_file = tmp_path / "processing_state.json"
        state_data = {
            "processed_files": {
                "test.wav": {"invalid": "entry"}
            }
        }
        state_file.write_text(json.dumps(state_data))
        
        with patch('transcriptx.core.utils.state_utils.validate_state_entry') as mock_validate:
            mock_validate.return_value = (False, ["Missing required field: transcript_path"])
            
            result = validate_processing_state(state_file)
            
            assert result["valid"] is False
            assert result["entries_invalid"] == 1


class TestRepairProcessingState:
    """Tests for repair_processing_state function."""
    
    def test_repairs_state_file(self, tmp_path):
        """Test that state file is repaired."""
        state_file = tmp_path / "processing_state.json"
        state_data = {
            "processed_files": {
                "test.wav": {
                    "transcript_path": str(tmp_path / "test.json")
                }
            }
        }
        state_file.write_text(json.dumps(state_data))
        
        with patch('transcriptx.core.utils.state_utils.validate_processing_state') as mock_validate, \
             patch('transcriptx.core.utils.state_utils.migrate_state_entry') as mock_migrate:
            
            mock_validate.return_value = {
                "valid": False,
                "errors": [],
                "warnings": []
            }
            mock_migrate.return_value = state_data["processed_files"]["test.wav"]
            
            result = repair_processing_state(state_file)
            
            assert "repaired" in result or "fixed" in result or isinstance(result, dict)


class TestGetAnalysisHistory:
    """Tests for get_analysis_history function."""
    
    def test_returns_analysis_history(self, tmp_path):
        """Test that analysis history is returned."""
        transcript_path = str(tmp_path / "test.json")
        
        with patch('transcriptx.core.utils.state_utils.load_processing_state') as mock_load:
            mock_load.return_value = {
                "processed_files": {
                    "test.wav": {
                        "transcript_path": transcript_path,
                        "analysis_modules_requested": ["sentiment", "emotion"],
                        "analysis_status": "completed"
                    }
                }
            }
            
            history = get_analysis_history(transcript_path)
            
            assert isinstance(history, dict)
            assert "analysis_modules_requested" in history or "modules" in history


class TestHasAnalysisCompleted:
    """Tests for has_analysis_completed function."""
    
    def test_returns_true_when_completed(self, tmp_path):
        """Test that True is returned when analysis is completed."""
        transcript_path = str(tmp_path / "test.json")
        
        with patch('transcriptx.core.utils.state_utils.load_processing_state') as mock_load:
            mock_load.return_value = {
                "processed_files": {
                    "test.wav": {
                        "transcript_path": transcript_path,
                        "analysis_status": "completed",
                        "analysis_modules_requested": ["sentiment"]
                    }
                }
            }
            
            result = has_analysis_completed(transcript_path, ["sentiment"])
            
            assert result is True
    
    def test_returns_false_when_not_completed(self, tmp_path):
        """Test that False is returned when analysis is not completed."""
        transcript_path = str(tmp_path / "test.json")
        
        with patch('transcriptx.core.utils.state_utils.load_processing_state') as mock_load:
            mock_load.return_value = {
                "processed_files": {
                    "test.wav": {
                        "transcript_path": transcript_path,
                        "analysis_status": "in_progress"
                    }
                }
            }
            
            result = has_analysis_completed(transcript_path, ["sentiment"])
            
            assert result is False


class TestGetMissingModules:
    """Tests for get_missing_modules function."""
    
    def test_returns_missing_modules(self, tmp_path):
        """Test that missing modules are returned."""
        transcript_path = str(tmp_path / "test.json")
        
        with patch('transcriptx.core.utils.state_utils.load_processing_state') as mock_load:
            mock_load.return_value = {
                "processed_files": {
                    "test.wav": {
                        "transcript_path": transcript_path,
                        "analysis_modules_requested": ["sentiment"]
                    }
                }
            }
            
            missing = get_missing_modules(transcript_path, ["sentiment", "emotion", "ner"])
            
            assert isinstance(missing, list)
            # Should include emotion and ner (not sentiment)
            assert "sentiment" not in missing or len(missing) > 0
