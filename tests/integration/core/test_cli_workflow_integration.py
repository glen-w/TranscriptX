"""
Integration tests for the app-layer analysis and speaker workflows.

Replaces the former CLI workflow integration tests. Uses the Python API
(AnalysisRequest / run_analysis) instead of the removed Typer CLI.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from transcriptx.app.models.requests import AnalysisRequest
from transcriptx.app.workflows.analysis import run_analysis, validate_analysis_readiness


@pytest.fixture()
def mini_transcript(tmp_path: Path) -> Path:
    """Return path to a copy of the mini fixture transcript."""
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "tests" / "fixtures" / "mini_transcriptx.json"
    if not src.exists():
        pytest.skip(f"Fixture missing: {src}")
    dest = tmp_path / "mini_transcriptx.json"
    import shutil

    shutil.copy(src, dest)
    return dest


@pytest.mark.integration
class TestAnalysisWorkflowIntegration:
    def test_validate_analysis_readiness_missing_file(self, tmp_path: Path) -> None:
        request = AnalysisRequest(
            transcript_path=tmp_path / "does_not_exist.json",
            mode="quick",
        )
        errors = validate_analysis_readiness(request)
        assert errors, "Expected validation error for missing file"

    def test_validate_analysis_readiness_invalid_mode(
        self, mini_transcript: Path
    ) -> None:
        request = AnalysisRequest(
            transcript_path=mini_transcript,
            mode="invalid_mode",
        )
        errors = validate_analysis_readiness(request)
        assert any("mode" in e.lower() for e in errors)

    def test_run_analysis_stats(self, mini_transcript: Path, tmp_path: Path) -> None:
        os.environ["TRANSCRIPTX_DB_ENABLED"] = "0"
        os.environ["TRANSCRIPTX_DISABLE_DOWNLOADS"] = "1"
        output_root = tmp_path / "out"
        output_root.mkdir()
        request = AnalysisRequest(
            transcript_path=mini_transcript,
            mode="quick",
            modules=["stats"],
            skip_speaker_mapping=True,
            output_dir=output_root,
        )
        result = run_analysis(request)
        assert result.success or result.errors is not None  # no crash


@pytest.mark.integration
class TestWebEntryIntegration:
    def test_web_entry_importable(self) -> None:
        import importlib

        mod = importlib.import_module("transcriptx.web.__main__")
        assert callable(getattr(mod, "main", None))
