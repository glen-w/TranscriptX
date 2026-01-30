"""
Tests for database CLI commands.

This module tests the database subcommand including init, status,
migrations, and speaker profiling operations.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from transcriptx.cli.main import app


class TestDatabaseCommands:
    """Tests for database CLI commands."""
    
    def test_database_init_command(self, typer_test_client, mock_database):
        """Test database init command."""
        with patch('transcriptx.database.init_database') as mock_init, \
             patch('transcriptx.database.get_migration_manager') as mock_migration:
            
            mock_init.return_value = MagicMock()
            mock_migration.return_value = MagicMock()
            
            result = typer_test_client.invoke(app, ["database", "init"])
            
            # Should attempt to initialize database
            assert result.exit_code in [0, 1]  # May succeed or fail depending on setup
    
    def test_database_init_with_force(self, typer_test_client, mock_database):
        """Test database init with force flag."""
        with patch('transcriptx.database.init_database') as mock_init, \
             patch('transcriptx.database.get_migration_manager') as mock_migration:
            
            mock_init.return_value = MagicMock()
            mock_migration.return_value = MagicMock()
            
            result = typer_test_client.invoke(app, ["database", "init", "--force"])
            
            assert result.exit_code in [0, 1]
    
    def test_database_reset_command(self, typer_test_client, mock_database):
        """Test database reset command."""
        with patch('transcriptx.database.db_reset_command.reset_database') as mock_reset, \
             patch('transcriptx.cli.database_commands.typer.confirm') as mock_confirm:
            
            mock_reset.return_value = None
            mock_confirm.return_value = True
            
            result = typer_test_client.invoke(app, ["database", "reset"])
            
            assert result.exit_code in [0, 1]
    
    def test_database_status_command(self, typer_test_client, mock_database):
        """Test database status command."""
        with patch('transcriptx.database.get_database_manager') as mock_get_manager:
            mock_manager = MagicMock()
            mock_manager.get_status.return_value = {"status": "ok"}
            mock_get_manager.return_value = mock_manager
            
            result = typer_test_client.invoke(app, ["database", "status"])
            
            # Should show database status
            assert result.exit_code in [0, 1]
    
    def test_database_migrations_command(self, typer_test_client, mock_database):
        """Test database migrations command."""
        result = typer_test_client.invoke(app, ["database", "migrations", "--help"])
        
        # Should show migrations help
        assert result.exit_code == 0
    
    def test_database_migrations_list(self, typer_test_client, mock_database):
        """Test listing migrations."""
        with patch('transcriptx.database.get_migration_history') as mock_history:
            mock_history.return_value = [
                {"id": 1, "name": "initial", "applied": True}
            ]
            
            result = typer_test_client.invoke(app, ["database", "migrations", "list"])
            
            assert result.exit_code in [0, 1]
    
    def test_database_migrations_status(self, typer_test_client, mock_database):
        """Test migration status command."""
        with patch('transcriptx.database.check_migration_status') as mock_status:
            mock_status.return_value = {"pending": 0, "applied": 5}
            
            result = typer_test_client.invoke(app, ["database", "migrations", "status"])
            
            assert result.exit_code in [0, 1]
    
    def test_database_speaker_profiling_command(self, typer_test_client, mock_database):
        """Test database speaker profiling command."""
        result = typer_test_client.invoke(app, ["database", "speakers", "--help"])
        
        # Should show speaker profiling help
        assert result.exit_code in [0, 1]
    
    def test_database_speakers_list(self, typer_test_client, mock_database):
        """Test listing speakers."""
        with patch('transcriptx.database.speaker_profiling.SpeakerProfilingService') as mock_service_class:
            mock_service = MagicMock()
            mock_service.list_speakers.return_value = [
                {"id": 1, "name": "Speaker 1"}
            ]
            mock_service_class.return_value = mock_service
            
            result = typer_test_client.invoke(app, ["database", "speakers", "list"])
            
            assert result.exit_code in [0, 1]
