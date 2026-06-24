"""Partial-run containment when deterministic modules succeed and LLM modules fail."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.llm.errors import LLM_UNAVAILABLE, LLMUnavailableError
from transcriptx.core.pipeline.dag_execution_adapter import execute_single_module
from transcriptx.core.pipeline.dag_pipeline import DAGPipeline, ModuleExecOutcome
from transcriptx.core.pipeline.manifest_builder import build_run_results_summary
from transcriptx.core.pipeline.module_registry import get_module_info
from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes
from transcriptx.core.utils.config.main import TranscriptXConfig
from transcriptx.core.utils.module_result import (
    build_module_result,
    now_iso,
)


@pytest.mark.unit
def test_summary_succeeds_llm_summary_fails_partial_run(tmp_path, temp_transcript_file):
    summary_info = get_module_info("summary")
    llm_info = get_module_info("llm_summary")
    assert summary_info is not None and llm_info is not None

    summary_artifact = (
        tmp_path / "out" / "summary" / "data" / "global" / "mini_summary.json"
    )
    summary_artifact.parent.mkdir(parents=True, exist_ok=True)
    summary_artifact.write_text(
        json.dumps({"overview": {"paragraph": "deterministic"}}),
        encoding="utf-8",
    )

    class _SummaryOk:
        def run_from_context(self, context):
            return build_module_result(
                module_name="summary",
                status="success",
                started_at=now_iso(),
                finished_at=now_iso(),
                artifacts=[{"path": str(summary_artifact), "type": "json"}],
                metrics={"duration_seconds": 0.1},
                payload_type="analysis_results",
                payload={"overview": {"paragraph": "deterministic"}},
            )

    class _LlmFail:
        def run_from_context(self, _context):
            raise LLMUnavailableError("daemon down")

    pipeline = SimpleNamespace(
        logger=MagicMock(),
        _module_progress_heartbeat=lambda *_a, **_k: None,
    )
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    module_results = {}
    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        summary_outcome = execute_single_module(
            pipeline,
            module_name="summary",
            node=SimpleNamespace(
                function=_SummaryOk,
                description=summary_info.description,
                requirements=summary_info.requirements,
            ),
            transcript_path=str(temp_transcript_file),
            context=MagicMock(),
            requirements_resolver=None,
            named_speaker_count=2,
        )
        llm_outcome = execute_single_module(
            pipeline,
            module_name="llm_summary",
            node=SimpleNamespace(
                function=_LlmFail,
                description=llm_info.description,
                requirements=llm_info.requirements,
            ),
            transcript_path=str(temp_transcript_file),
            context=MagicMock(),
            requirements_resolver=None,
            named_speaker_count=2,
        )

    assert summary_outcome.status == "success"
    assert llm_outcome.status == "failed"
    assert llm_outcome.module_result is not None
    module_results["summary"] = summary_outcome.module_result
    module_results["llm_summary"] = llm_outcome.module_result

    run_results = build_run_results_summary(
        run_id="run-partial",
        transcript_key="mini",
        modules_enabled=["summary", "llm_summary"],
        modules_run=["summary"],
        skipped_modules=[],
        errors=["llm_summary: daemon down"],
        module_results=module_results,
    )
    assert run_results["modules_failed"] == ["llm_summary"]
    canonical = {row.module_id: row for row in project_canonical_outcomes(run_results)}
    assert canonical["summary"].status == "succeeded"
    assert canonical["llm_summary"].status == "failed"
    assert canonical["llm_summary"].error_code == LLM_UNAVAILABLE

    llm_json = (
        tmp_path / "out" / "llm_summary" / "data" / "global" / "mini_llm_summary.json"
    )
    assert summary_artifact.exists()
    assert not llm_json.exists()


@pytest.mark.unit
def test_dag_pipeline_partial_when_llm_module_fails(tmp_path, temp_transcript_file):
    p = DAGPipeline()
    p.add_module("summary", "Summary", "light", [], MagicMock())
    p.add_module("llm_summary", "LLM Summary", "medium", [], MagicMock())
    p.finalize()

    success = ModuleExecOutcome(
        status="success",
        module_result={"status": "success"},
        duration_ms=1.0,
    )
    failed = ModuleExecOutcome(
        status="failed",
        error="daemon down",
        module_result={
            "status": "error",
            "error": {"error_code": LLM_UNAVAILABLE, "error_message": "daemon down"},
        },
        duration_ms=1.0,
    )

    def _execute_side_effect(**kwargs):
        name = kwargs.get("module_name")
        if name == "summary":
            return success
        if name == "llm_summary":
            return failed
        return success

    ctx = MagicMock()
    ctx.validate.return_value = True
    ctx.get_segments.return_value = [{"speaker": "A", "text": "hello"}]
    ctx.get_speaker_map.return_value = {"SPEAKER_00": "A"}

    with (
        patch.object(p, "_execute_single_module", side_effect=_execute_side_effect),
        patch("transcriptx.core.pipeline.dag_pipeline.validate_transcript_file"),
        patch("transcriptx.core.pipeline.dag_pipeline.validate_output_directory"),
    ):
        result = p.execute_pipeline(
            transcript_path=str(temp_transcript_file),
            selected_modules=["summary", "llm_summary"],
            output_dir=str(tmp_path / "out"),
            context=ctx,
            named_speaker_count=1,
        )

    assert "summary" in result["modules_run"]
    assert "llm_summary" not in result["modules_run"]
    assert result["errors"]
    assert "llm_summary" in result.get("module_results", {})
