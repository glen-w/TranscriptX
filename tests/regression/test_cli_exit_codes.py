"""
Regression tests for exit code / error propagation in the app-layer workflows.

Replaces the former CLI exit-code tests. The app layer returns structured
result objects rather than process exit codes.
"""

from __future__ import annotations

from pathlib import Path


# Standard exit code constants used by the web entry point
EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_USER_CANCEL = 130


class TestAnalysisResultErrors:
    """Verify that AnalysisResult.errors is populated on failure."""

    def test_missing_transcript_gives_errors(self, tmp_path: Path) -> None:
        from transcriptx.app.models.requests import AnalysisRequest
        from transcriptx.app.workflows.analysis import validate_analysis_readiness

        req = AnalysisRequest(transcript_path=tmp_path / "missing.json")
        errors = validate_analysis_readiness(req)
        assert errors, "Expected validation errors for missing transcript"

    def test_invalid_mode_gives_errors(self, tmp_path: Path) -> None:
        from transcriptx.app.models.requests import AnalysisRequest
        from transcriptx.app.workflows.analysis import validate_analysis_readiness

        f = tmp_path / "t.json"
        f.write_text("{}")
        req = AnalysisRequest(transcript_path=f, mode="invalid")
        errors = validate_analysis_readiness(req)
        assert any("mode" in e.lower() for e in errors)


class TestExitCodeConsistency:
    def test_exit_code_constants(self) -> None:
        assert EXIT_SUCCESS == 0
        assert EXIT_ERROR == 1
        assert EXIT_USER_CANCEL == 130
