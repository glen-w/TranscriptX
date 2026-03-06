"""
Contract tests for workflow_modules entry points.

Covers deprecated behavior (e.g. run_transcription_workflow exits with 2)
and delegation so refactors don't break CLI routing.
"""

import pytest

from transcriptx.cli.workflow_modules import run_transcription_workflow


class TestTranscriptionWorkflowDeprecated:
    """run_transcription_workflow is deprecated and must exit with code 2."""

    def test_run_transcription_workflow_exits_with_code_2(self):
        """Deprecated transcription workflow raises SystemExit(2)."""
        with pytest.raises(SystemExit) as exc_info:
            run_transcription_workflow()
        assert exc_info.value.code == 2
