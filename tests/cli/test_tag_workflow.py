"""
Tests for tag workflow execution.

This module tests tag loading, editing, and state management.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from transcriptx.cli.tag_workflow import (
    load_tags_for_transcript,
    offer_and_edit_tags,
    update_tags_in_state,
)


class TestLoadTagsForTranscript:
    """Tests for load_tags_for_transcript function."""
    
    def test_loads_tags_from_state(self, tmp_path):
        """Test that tags are loaded from processing state."""
        transcript_path = str(tmp_path / "test.json")
        
        state_data = {
            "processed_files": {
                "test.wav": {
                    "transcript_path": transcript_path,
                    "extract_tags": {
                        "tags": ["meeting", "discussion"],
                        "tag_details": {"meeting": {"confidence": 0.9}}
                    },
                    "tags": ["meeting", "discussion", "custom"]
                }
            }
        }
        
        with patch('transcriptx.cli.tag_workflow.load_processing_state') as mock_load:
            mock_load.return_value = state_data
            
            result = load_tags_for_transcript(transcript_path)
            
            assert "auto_tags" in result
            assert "current_tags" in result
            assert "meeting" in result["auto_tags"]
            assert "custom" in result["current_tags"]
    
    def test_extracts_tags_when_not_in_state(self, tmp_path):
        """Test that tags are extracted when not in state."""
        transcript_path = str(tmp_path / "test.json")
        transcript_data = {
            "segments": [
                {"speaker": "SPEAKER_00", "text": "Hello world", "start": 0.0, "end": 1.0}
            ]
        }
        Path(transcript_path).write_text(json.dumps(transcript_data))
        
        with patch('transcriptx.cli.tag_workflow.load_processing_state') as mock_load, \
             patch('transcriptx.cli.tag_workflow.extract_tags') as mock_extract:
            
            mock_load.return_value = {"processed_files": {}}
            mock_extract.return_value = {
                "tags": ["auto_tag"],
                "tag_details": {}
            }
            
            result = load_tags_for_transcript(transcript_path)
            
            assert "auto_tags" in result
            mock_extract.assert_called()
    
    def test_resolves_transcript_path(self, tmp_path):
        """Test that transcript path is resolved."""
        transcript_path = "test.json"  # Relative path
        
        with patch('transcriptx.cli.tag_workflow.load_processing_state') as mock_load, \
             patch('transcriptx.cli.tag_workflow.resolve_file_path') as mock_resolve:
            
            mock_load.return_value = {"processed_files": {}}
            mock_resolve.return_value = str(tmp_path / "test.json")
            
            result = load_tags_for_transcript(transcript_path)
            
            mock_resolve.assert_called()


class TestOfferAndEditTags:
    """Tests for offer_and_edit_tags function."""
    
    def test_offers_tag_editing(self, tmp_path):
        """Test that tag editing is offered."""
        transcript_path = str(tmp_path / "test.json")
        
        with patch('transcriptx.cli.tag_workflow.load_tags_for_transcript') as mock_load, \
             patch('transcriptx.cli.tag_workflow.manage_tags_interactive') as mock_manage, \
             patch('transcriptx.cli.tag_workflow.questionary') as mock_q:
            
            mock_load.return_value = {
                "auto_tags": ["meeting"],
                "tag_details": {},
                "current_tags": ["meeting"],
                "transcript_path": transcript_path
            }
            mock_q.confirm.return_value.ask.return_value = True
            mock_manage.return_value = {
                "tags": ["meeting", "custom"],
                "tag_details": {}
            }
            
            result = offer_and_edit_tags(transcript_path)
            
            assert result is not None
            assert "tags" in result
    
    def test_skips_when_user_declines(self, tmp_path):
        """Test that editing is skipped when user declines."""
        transcript_path = str(tmp_path / "test.json")
        
        with patch('transcriptx.cli.tag_workflow.load_tags_for_transcript') as mock_load, \
             patch('transcriptx.cli.tag_workflow.questionary') as mock_q:
            
            mock_load.return_value = {
                "auto_tags": ["meeting"],
                "current_tags": ["meeting"],
                "transcript_path": transcript_path
            }
            mock_q.confirm.return_value.ask.return_value = False
            
            result = offer_and_edit_tags(transcript_path, auto_prompt=True)
            
            # Should return None or current tags
            assert result is None or isinstance(result, dict)
    
    def test_skips_prompt_in_batch_mode(self, tmp_path):
        """Test that prompt is skipped in batch mode."""
        transcript_path = str(tmp_path / "test.json")
        
        with patch('transcriptx.cli.tag_workflow.load_tags_for_transcript') as mock_load:
            mock_load.return_value = {
                "auto_tags": ["meeting"],
                "current_tags": ["meeting"],
                "transcript_path": transcript_path
            }
            
            result = offer_and_edit_tags(transcript_path, batch_mode=True, auto_prompt=True)
            
            # Should return tags without prompting
            assert result is not None or isinstance(result, dict)


class TestSaveTagsToState:
    """Tests for save_tags_to_state function."""
    
    def test_saves_tags_to_state(self, tmp_path):
        """Test that tags are saved to processing state."""
        transcript_path = str(tmp_path / "test.json")
        tags = ["meeting", "discussion"]
        tag_details = {"meeting": {"confidence": 0.9}}
        
        state_data = {
            "processed_files": {
                "test.wav": {
                    "transcript_path": transcript_path
                }
            }
        }
        
        with patch('transcriptx.cli.tag_workflow.load_processing_state') as mock_load, \
             patch('transcriptx.cli.tag_workflow.save_processing_state') as mock_save:
            
            mock_load.return_value = state_data.copy()
            
            from transcriptx.cli.tag_workflow import update_tags_in_state
            update_tags_in_state(transcript_path, tags, tag_details)
            
            # Should save state
            mock_save.assert_called_once()
            call_args = mock_save.call_args[0][0]
            assert "processed_files" in call_args
    
    def test_updates_existing_entry(self, tmp_path):
        """Test that existing entry is updated."""
        transcript_path = str(tmp_path / "test.json")
        tags = ["new_tag"]
        
        state_data = {
            "processed_files": {
                "test.wav": {
                    "transcript_path": transcript_path,
                    "tags": ["old_tag"]
                }
            }
        }
        
        with patch('transcriptx.cli.tag_workflow.load_processing_state') as mock_load, \
             patch('transcriptx.cli.tag_workflow.save_processing_state') as mock_save:
            
            mock_load.return_value = state_data.copy()
            
            from transcriptx.cli.tag_workflow import update_tags_in_state
            update_tags_in_state(transcript_path, tags, {})
            
            # Should update tags
            call_args = mock_save.call_args[0][0]
            entry = call_args["processed_files"]["test.wav"]
            assert "new_tag" in entry.get("tags", [])
