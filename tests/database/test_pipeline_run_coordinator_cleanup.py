"""
Tests for PipelineRunCoordinator resource cleanup.
"""

from unittest.mock import MagicMock, patch

import pytest

from transcriptx.database.pipeline_run_service import PipelineRunCoordinator


@pytest.mark.database
def test_pipeline_run_coordinator_close_cleans_resources():
    """PipelineRunCoordinator.close should close ingestion service and session."""
    mock_session = MagicMock()
    mock_ingestion = MagicMock()

    with (
        patch(
            "transcriptx.database.pipeline_run_service.get_session",
            return_value=mock_session,
        ),
        patch(
            "transcriptx.database.pipeline_run_service.TranscriptIngestionService",
            return_value=mock_ingestion,
        ),
        patch("transcriptx.database.pipeline_run_service.require_up_to_date_schema"),
    ):
        coordinator = PipelineRunCoordinator(
            transcript_path="/tmp/test.json",
            selected_modules=["sentiment"],
            pipeline_config={"modules": ["sentiment"]},
        )

        coordinator.close()

    mock_ingestion.close.assert_called_once()
    mock_session.close.assert_called_once()
