"""Tests for app/workflows - prompt-free orchestration."""

import pytest
from pathlib import Path

from transcriptx.app.workflows.analysis import run_analysis, validate_analysis_readiness
from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.progress import NullProgress


def test_validate_analysis_readiness_nonexistent():
    """Validation fails for non-existent transcript."""
    req = AnalysisRequest(transcript_path=Path("/nonexistent/path.json"))
    errors = validate_analysis_readiness(req)
    assert len(errors) > 0
    assert "not found" in errors[0].lower()


def test_validate_analysis_readiness_invalid_mode():
    """Validation fails for invalid mode."""
    req = AnalysisRequest(transcript_path=Path("."), mode="invalid")
    errors = validate_analysis_readiness(req)
    assert any("mode" in e.lower() for e in errors)


def test_run_analysis_nonexistent_returns_failed_result():
    """run_analysis returns failed result for non-existent path."""
    req = AnalysisRequest(transcript_path=Path("/nonexistent/path.json"))
    result = run_analysis(req, progress=NullProgress())
    assert not result.success
    assert result.status == "failed"
    assert len(result.errors) > 0
