"""Batch request copies llm_model_selection onto child AnalysisRequests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from transcriptx.app.models.requests import AnalysisRequest, BatchAnalysisRequest
from transcriptx.app.models.results import AnalysisResult
from transcriptx.app.workflows.batch import run_batch_analysis
from transcriptx.core.analysis.llm_support.model_selection import LlmModelSelection


def test_batch_forwards_llm_model_selection(tmp_path: Path):
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    selection = LlmModelSelection(mode="shared", shared_model="batch-model")
    captured: list[AnalysisRequest] = []

    def _fake_run(request: AnalysisRequest, progress=None):
        captured.append(request)
        return AnalysisResult(
            success=True,
            run_dir=tmp_path / "run",
            manifest_path=tmp_path / "run" / "manifest.json",
            modules_executed=["stats"],
            warnings=[],
            errors=[],
            status="completed",
        )

    with patch("transcriptx.app.workflows.batch.run_analysis", side_effect=_fake_run):
        result = run_batch_analysis(
            BatchAnalysisRequest(
                transcript_paths=[transcript],
                analysis_mode="quick",
                selected_modules=["stats"],
                llm_model_selection=selection,
            )
        )

    assert result.success
    assert len(captured) == 1
    assert captured[0].llm_model_selection == selection
