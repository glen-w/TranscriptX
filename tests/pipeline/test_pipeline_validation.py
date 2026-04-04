"""
Unit tests for pipeline validation (run_analysis_pipeline error branches, target resolution).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.pipeline.pipeline import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import (
    GroupRef,
    TranscriptRef,
)


class TestRunAnalysisPipelineValidation:
    """Tests for run_analysis_pipeline input validation."""

    def test_no_target_raises(self) -> None:
        """run_analysis_pipeline raises when target and transcript_path are both None."""
        with pytest.raises(ValueError, match="Analysis target must be provided"):
            run_analysis_pipeline(
                target=None,
                selected_modules=["stats"],
                transcript_path=None,
            )

    def test_no_selected_modules_raises(self, tmp_path: Path) -> None:
        """run_analysis_pipeline raises when selected_modules is None (without manifest)."""
        transcript_file = tmp_path / "transcript.json"
        transcript_file.write_text('{"segments": []}')

        with pytest.raises(ValueError, match="selected_modules must be provided"):
            run_analysis_pipeline(
                target=TranscriptRef(path=str(transcript_file)),
                selected_modules=None,
            )


class TestTranscriptRefValidation:
    """Tests for TranscriptRef validation."""

    def test_must_set_path(self) -> None:
        """TranscriptRef requires path."""
        with pytest.raises(TypeError, match="missing.*argument"):
            TranscriptRef()

    def test_path_only_valid(self) -> None:
        """TranscriptRef with path is valid."""
        ref = TranscriptRef(path="/path/to/file.json")
        assert ref.path == "/path/to/file.json"

    def test_empty_path_raises(self) -> None:
        """TranscriptRef with empty path raises."""
        with pytest.raises(ValueError, match="must set path"):
            TranscriptRef(path="")


class TestGroupRefValidation:
    """Tests for GroupRef validation."""

    def test_must_set_path(self) -> None:
        """GroupRef requires path."""
        with pytest.raises(TypeError, match="missing.*argument"):
            GroupRef()

    def test_path_valid(self) -> None:
        """GroupRef with path is valid."""
        ref = GroupRef(path="/path/to/group.json")
        assert ref.path == "/path/to/group.json"
