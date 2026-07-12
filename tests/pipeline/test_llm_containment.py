"""Pipeline containment tests for LLM module failures."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.llm.errors import LLMUnavailableError
from transcriptx.core.pipeline.dag_execution_adapter import execute_single_module
from transcriptx.core.pipeline.module_registry import get_module_info
from transcriptx.core.utils.config.main import TranscriptXConfig


@pytest.mark.unit
def test_llm_failure_does_not_prevent_adapter_from_returning_failed_outcome() -> None:
    class _FailingLLM:
        def run_from_context(self, _context):
            raise LLMUnavailableError("daemon down")

    info = get_module_info("llm_summary")
    assert info is not None
    pipeline = SimpleNamespace(
        logger=MagicMock(),
        _module_progress_heartbeat=lambda *_a, **_k: None,
    )
    node = SimpleNamespace(
        function=_FailingLLM,
        description=info.description,
        requirements=info.requirements,
    )
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        outcome = execute_single_module(
            pipeline,
            module_name="llm_summary",
            node=node,
            transcript_path="t.json",
            context=MagicMock(),
            requirements_resolver=None,
            named_speaker_count=2,
        )

    assert outcome.status == "failed"
    assert outcome.module_result is not None
    assert outcome.module_result.get("artifacts") == []
    assert outcome.module_result["error"]["error_code"] == "llm_unavailable"


@pytest.mark.unit
def test_disabled_llm_modules_skip_without_client(tmp_path) -> None:
    from transcriptx.core.pipeline.dag_pipeline_planning import (
        compute_review_before_run_for_pipeline,
    )
    from transcriptx.core.pipeline.module_registry import get_module_registry

    pipeline = SimpleNamespace(
        _finalized=True,
        nodes={},
        logger=MagicMock(),
        finalize=lambda: None,
        preflight_check=lambda _mods: {
            "skipped_modules": [],
            "missing_dependencies": [],
        },
    )
    registry = get_module_registry()
    for name in ("llm_summary", "narrative_summary", "llm_speaker_summary"):
        info = registry.get_module_info(name)
        if info:
            pipeline.nodes[name] = SimpleNamespace(
                description=info.description,
                requirements=info.requirements,
            )

    def _resolve_dependencies(selected):
        from transcriptx.core.pipeline.contracts import (
            RegistryModuleSnapshot,
            RegistrySnapshot,
        )

        modules = {
            n: RegistryModuleSnapshot(
                name=n,
                dependencies=list(i.dependencies),
                category=i.category,
            )
            for n in registry.get_available_modules()
            if (i := registry.get_module_info(n)) is not None
        }
        from transcriptx.core.pipeline.dag_planner import DAGPlanner

        return (
            DAGPlanner()
            .plan(selected, RegistrySnapshot(modules=modules))
            .deterministic_order
        )

    pipeline.resolve_dependencies = _resolve_dependencies
    cfg = TranscriptXConfig()
    cfg.llm.enabled = False
    cfg.llm.provider = "null"

    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        review = compute_review_before_run_for_pipeline(
            pipeline,
            transcript_path=str(tmp_path / "mini.json"),
            selected_modules=[
                "llm_summary",
                "narrative_summary",
                "llm_speaker_summary",
            ],
            output_dir=str(tmp_path / "out"),
        )

    skipped = {row["module"]: row["reason"] for row in review["modules_skipped"]}
    assert skipped.get("llm_summary") == "LLM disabled"
    assert skipped.get("narrative_summary") == "LLM disabled"
    assert skipped.get("llm_speaker_summary") == "LLM disabled"
    assert review["modules_will_run"] == []
