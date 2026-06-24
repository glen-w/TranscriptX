"""Tests for TranscriptionController delegation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.app.controllers.transcription_controller import TranscriptionController
from transcriptx.app.models.errors import WorkflowExecutionError
from transcriptx.app.models.requests import (
    TranscriptionConversionOptions,
    TranscriptionOptions,
    TranscriptionRequest,
)
from transcriptx.app.models.results import TranscriptionBatchResult


@pytest.mark.unit
class TestTranscriptionController:
    @patch("transcriptx.app.controllers.transcription_controller.run_transcription_workflow")
    def test_controller_returns_batch_result(self, mock_workflow, tmp_path: Path):
        expected = TranscriptionBatchResult(
            job_id="abc",
            success=True,
            file_results=[],
            succeeded_count=0,
            failed_count=0,
            output_dir=tmp_path,
        )
        mock_workflow.return_value = expected
        request = TranscriptionRequest(
            input_paths=[tmp_path / "a.wav"],
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
        )
        result = TranscriptionController().run_transcription(request)
        assert result is expected
        mock_workflow.assert_called_once()

    @patch("transcriptx.app.controllers.transcription_controller.run_transcription_workflow")
    def test_controller_raises_workflow_execution_error(self, mock_workflow):
        mock_workflow.side_effect = RuntimeError("boom")
        request = TranscriptionRequest(
            input_paths=[Path("/tmp/a.wav")],
            transcription_options=TranscriptionOptions(
                provider_id="whispermlx",
                model="large-v3",
                language="en",
                diarize=False,
            ),
            conversion_options=TranscriptionConversionOptions(),
        )
        with pytest.raises(WorkflowExecutionError, match="boom"):
            TranscriptionController().run_transcription(request)
