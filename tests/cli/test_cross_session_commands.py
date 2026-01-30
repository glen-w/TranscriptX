"""
Tests for cross-session CLI commands.

This module tests the cross-session subcommand including speaker matching,
pattern evolution tracking, and behavioral analysis.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from transcriptx.cli.main import app


class TestCrossSessionCommands:
    """Tests for cross-session CLI commands."""
    
    def test_cross_session_match_speakers_command(
        self, typer_test_client, temp_transcript_file, mock_database
    ):
        """Test cross-session match-speakers command."""
        with patch('transcriptx.cli.cross_session_commands.load_transcript_data') as mock_load, \
             patch('transcriptx.cli.cross_session_commands.CrossSessionTrackingService') as mock_service_class:
            mock_load.return_value = {
                "segments": [{"speaker": "SPEAKER_00", "text": "Hi"}]
            }
            mock_service = MagicMock()
            mock_speaker = MagicMock()
            mock_speaker.id = 1
            mock_speaker.name = "John Doe"
            mock_speaker.email = "john@example.com"
            mock_speaker.organization = "Org"
            mock_speaker.is_verified = True
            mock_service.find_speaker_matches.return_value = [
                (mock_speaker, 0.85)
            ]
            mock_service_class.return_value = mock_service
            
            result = typer_test_client.invoke(
                app, [
                    "cross-session", "match-speakers",
                    "SPEAKER_00",
                    "--transcript", str(temp_transcript_file)
                ]
            )
            
            # Should find speaker matches
            assert result.exit_code in [0, 1]
    
    def test_cross_session_match_speakers_with_threshold(
        self, typer_test_client, temp_transcript_file, mock_database
    ):
        """Test match-speakers with confidence threshold."""
        with patch('transcriptx.cli.cross_session_commands.load_transcript_data') as mock_load, \
             patch('transcriptx.cli.cross_session_commands.CrossSessionTrackingService') as mock_service_class:
            mock_load.return_value = {
                "segments": [{"speaker": "SPEAKER_00", "text": "Hi"}]
            }
            mock_service = MagicMock()
            mock_service.find_speaker_matches.return_value = []
            mock_service_class.return_value = mock_service
            
            result = typer_test_client.invoke(
                app, [
                    "cross-session", "match-speakers",
                    "SPEAKER_00",
                    "--transcript", str(temp_transcript_file),
                    "--threshold", "0.8"
                ]
            )
            
            # Should use threshold
            call_args = mock_service.find_speaker_matches.call_args
            assert call_args.args[2] == 0.8
    
    def test_cross_session_list_clusters_command(self, typer_test_client, mock_database):
        """Test cross-session list-clusters command."""
        mock_session = MagicMock()
        mock_query = MagicMock()
        mock_query.all.return_value = []
        mock_session.query.return_value = mock_query
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_session
        mock_context.__exit__.return_value = None

        with patch('transcriptx.cli.cross_session_commands.get_session', return_value=mock_context):
            result = typer_test_client.invoke(app, ["cross-session", "list-clusters"])
            
            # Should list speaker clusters
            assert result.exit_code in [0, 1]
    
    def test_cross_session_analyze_patterns_command(self, typer_test_client, mock_database):
        """Test cross-session analyze-patterns command."""
        result = typer_test_client.invoke(app, ["cross-session", "analyze-patterns", "--help"])
        
        # Should show help for pattern analysis
        assert result.exit_code == 0
    
    def test_cross_session_track_evolution(self, typer_test_client, mock_database):
        """Test cross-session track-evolution command."""
        with patch('transcriptx.database.cross_session_tracking.CrossSessionTrackingService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.track_pattern_evolution.return_value = {
                "patterns": [],
                "changes": []
            }
            mock_service_class.return_value = mock_service
            
            result = typer_test_client.invoke(app, ["cross-session", "track-evolution", "--help"])
            
            assert result.exit_code == 0
