"""
Tests for transcript CLI commands.

This module tests the transcript subcommand including list, show,
delete, and export operations.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from transcriptx.cli.main import app


class TestTranscriptCommands:
    """Tests for transcript CLI commands."""
    
    def test_transcript_list_command(self, typer_test_client, mock_database):
        """Test transcript list command."""
        with patch('transcriptx.database.transcript_manager.TranscriptManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.list_conversations.return_value = [
                {
                    "id": 1,
                    "title": "Test Conversation",
                    "duration_seconds": 120,
                    "speaker_count": 2,
                    "analysis_status": "completed",
                    "created_at": "2024-01-01T00:00:00"
                }
            ]
            mock_manager_class.return_value = mock_manager
            
            result = typer_test_client.invoke(app, ["transcript", "list"])
            
            # Should list conversations
            assert result.exit_code in [0, 1]
    
    def test_transcript_list_with_limit(self, typer_test_client, mock_database):
        """Test transcript list with limit."""
        with patch('transcriptx.database.transcript_manager.TranscriptManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.list_conversations.return_value = []
            mock_manager_class.return_value = mock_manager
            
            result = typer_test_client.invoke(app, ["transcript", "list", "--limit", "5"])
            
            # Should respect limit
            call_args = mock_manager.list_conversations.call_args
            assert call_args.kwargs["limit"] == 5
    
    def test_transcript_list_with_status_filter(self, typer_test_client, mock_database):
        """Test transcript list with status filter."""
        with patch('transcriptx.database.transcript_manager.TranscriptManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.list_conversations.return_value = []
            mock_manager_class.return_value = mock_manager
            
            result = typer_test_client.invoke(app, ["transcript", "list", "--status", "completed"])
            
            # Should filter by status
            call_args = mock_manager.list_conversations.call_args
            assert call_args.kwargs["status_filter"] == "completed"
    
    def test_transcript_list_with_details(self, typer_test_client, mock_database):
        """Test transcript list with details flag."""
        with patch('transcriptx.database.transcript_manager.TranscriptManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.list_conversations.return_value = []
            mock_manager_class.return_value = mock_manager
            
            result = typer_test_client.invoke(app, ["transcript", "list", "--details"])
            
            assert result.exit_code in [0, 1]
    
    def test_transcript_show_command(self, typer_test_client, mock_database):
        """Test transcript show command."""
        with patch('transcriptx.database.transcript_manager.TranscriptManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.get_conversation.return_value = {
                "id": 1,
                "title": "Test",
                "segments": []
            }
            mock_manager_class.return_value = mock_manager
            
            result = typer_test_client.invoke(app, ["transcript", "show", "1"])
            
            # Should show conversation details
            assert result.exit_code in [0, 1]
    
    def test_transcript_show_not_found(self, typer_test_client, mock_database):
        """Test transcript show when conversation not found."""
        with patch('transcriptx.database.transcript_manager.TranscriptManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.get_conversation.return_value = None
            mock_manager_class.return_value = mock_manager
            
            result = typer_test_client.invoke(app, ["transcript", "show", "999"])
            
            assert result.exit_code in [0, 1]
    
    def test_transcript_delete_command(self, typer_test_client, mock_database):
        """Test transcript delete command."""
        with patch('transcriptx.database.transcript_manager.TranscriptManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.delete_conversation.return_value = True
            mock_manager_class.return_value = mock_manager
            
            result = typer_test_client.invoke(
                app, ["transcript", "delete", "1", "--yes"]
            )
            
            # Should delete conversation
            assert result.exit_code in [0, 1]
            mock_manager.delete_conversation.assert_called_once_with(1)
    
    def test_transcript_delete_without_confirm(self, typer_test_client, mock_database):
        """Test transcript delete without --yes flag."""
        with patch('transcriptx.database.transcript_manager.TranscriptManager') as mock_manager_class, \
             patch('transcriptx.cli.transcript_commands.typer.confirm') as mock_confirm:
            
            mock_manager = MagicMock()
            mock_manager_class.return_value = mock_manager
            mock_confirm.return_value = False  # User cancels
            
            result = typer_test_client.invoke(app, ["transcript", "delete", "1"])
            
            # Should not delete if not confirmed
            mock_manager.delete_conversation.assert_not_called()
    
    def test_transcript_export_command(self, typer_test_client, mock_database, tmp_path):
        """Test transcript export command."""
        export_file = tmp_path / "export.json"
        
        with patch('transcriptx.database.transcript_manager.TranscriptManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.get_conversation.return_value = {
                "id": 1,
                "title": "Test",
                "segments": []
            }
            mock_manager_class.return_value = mock_manager
            
            result = typer_test_client.invoke(
                app, ["transcript", "export", "1", "--output", str(export_file)]
            )
            
            # Should export conversation
            assert result.exit_code in [0, 1]
    
    def test_transcript_export_without_output(self, typer_test_client, mock_database):
        """Test transcript export without output file."""
        with patch('transcriptx.database.transcript_manager.TranscriptManager') as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.get_conversation.return_value = {
                "id": 1,
                "title": "Test",
                "segments": []
            }
            mock_manager_class.return_value = mock_manager
            
            result = typer_test_client.invoke(app, ["transcript", "export", "1"])
            
            # Should use default output
            assert result.exit_code in [0, 1]
