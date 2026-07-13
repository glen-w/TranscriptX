"""Tests for requires_llm gating and dependency expansion."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.pipeline.dag_pipeline_run import llm_gate_skip_reason
from transcriptx.core.pipeline.dag_planner import DAGPlanner
from transcriptx.core.pipeline.module_registry import get_module_info
from transcriptx.core.utils.config.main import TranscriptXConfig


@pytest.mark.unit
def test_llm_gate_skip_when_disabled() -> None:
    info = SimpleNamespace(requires_llm=True)
    cfg = TranscriptXConfig()
    cfg.llm.enabled = False
    cfg.llm.provider = "null"
    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        assert llm_gate_skip_reason(info) == "LLM disabled"


@pytest.mark.unit
def test_llm_gate_none_when_enabled() -> None:
    info = SimpleNamespace(requires_llm=True)
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"
    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        assert llm_gate_skip_reason(info) is None


@pytest.mark.unit
def test_llm_modules_in_default_recommended_list() -> None:
    from transcriptx.core.pipeline.module_registry import get_default_modules

    modules = get_default_modules()
    assert "llm_summary" in modules
    assert "narrative_summary" in modules
    assert "llm_speaker_summary" in modules


@pytest.mark.unit
def test_narrative_summary_requires_llm_registered() -> None:
    info = get_module_info("narrative_summary")
    assert info is not None
    assert info.requires_llm is True
    assert "summary" in info.dependencies


@pytest.mark.unit
def test_llm_summary_requires_llm_registered() -> None:
    info = get_module_info("llm_summary")
    assert info is not None
    assert info.requires_llm is True


@pytest.mark.unit
def test_llm_speaker_summary_requires_llm_registered() -> None:
    info = get_module_info("llm_speaker_summary")
    assert info is not None
    assert info.requires_llm is True
    assert info.exclude_from_default is False


@pytest.mark.unit
def test_llm_action_items_requires_llm_registered() -> None:
    info = get_module_info("llm_action_items")
    assert info is not None
    assert info.requires_llm is True


@pytest.mark.unit
def test_lexical_diversity_registry_metadata() -> None:
    info = get_module_info("lexical_diversity")
    assert info is not None
    assert info.requires_llm is False
    from transcriptx.core.domain.module_requirements import Requirement

    assert Requirement.SEGMENTS in info.requirements
    assert Requirement.SPEAKER_LABELS in info.requirements
    assert Requirement.SEGMENT_TIMESTAMPS not in info.requirements


@pytest.mark.unit
def test_llm_action_items_registry_import() -> None:
    from transcriptx.core.analysis.llm_action_items import LLMActionItemsAnalysis

    module = LLMActionItemsAnalysis()
    assert module.module_name == "llm_action_items"


@pytest.mark.unit
def test_dag_planner_expands_narrative_summary_dependencies() -> None:
    from transcriptx.core.pipeline.contracts import (
        RegistryModuleSnapshot,
        RegistrySnapshot,
    )
    from transcriptx.core.pipeline.module_registry import get_module_registry

    registry = get_module_registry()
    modules = {
        name: RegistryModuleSnapshot(
            name=name,
            dependencies=list(info.dependencies),
            category=info.category,
        )
        for name in registry.get_available_modules()
        if (info := registry.get_module_info(name)) is not None
    }
    snapshot = RegistrySnapshot(modules=modules)
    plan = DAGPlanner().plan(["narrative_summary"], snapshot)
    assert "narrative_summary" in plan.runnable
    assert "summary" in plan.runnable
    order = plan.deterministic_order
    assert order.index("summary") < order.index("narrative_summary")


@pytest.mark.unit
def test_execute_single_module_skips_llm_module_when_disabled() -> None:
    from transcriptx.core.pipeline.dag_execution_adapter import execute_single_module
    from transcriptx.core.pipeline.module_registry import get_module_info

    pipeline = SimpleNamespace(logger=MagicMock())
    info = get_module_info("narrative_summary")
    assert info is not None
    node = SimpleNamespace(
        function=MagicMock(),
        description=info.description,
        requirements=info.requirements,
    )
    cfg = TranscriptXConfig()
    cfg.llm.enabled = False
    cfg.llm.provider = "null"

    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        outcome = execute_single_module(
            pipeline,
            module_name="narrative_summary",
            node=node,
            transcript_path="t.json",
            context=None,
            requirements_resolver=None,
            named_speaker_count=2,
        )

    assert outcome.status == "skipped"
    assert outcome.skip_reason == "LLM disabled"


@pytest.mark.unit
def test_execute_single_module_preserves_error_code_on_raise() -> None:
    from transcriptx.core.pipeline.dag_execution_adapter import execute_single_module
    from transcriptx.core.llm.errors import LLM_UNAVAILABLE, LLMUnavailableError

    class _RaisingModule:
        def run_from_context(self, _context):
            raise LLMUnavailableError("daemon down")

    pipeline = SimpleNamespace(
        logger=MagicMock(),
        _module_progress_heartbeat=lambda *_a, **_k: None,
    )
    node = SimpleNamespace(
        function=_RaisingModule,
        description="LLM Summary",
        requirements=[],
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
    assert outcome.module_result["error"]["error_code"] == LLM_UNAVAILABLE


@pytest.mark.unit
def test_review_before_run_skips_llm_module_when_disabled(tmp_path) -> None:
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
    for name in ("summary", "narrative_summary"):
        info = registry.get_module_info(name)
        fn = registry.get_module_function(name)
        if info and fn:
            pipeline.nodes[name] = SimpleNamespace(
                description=info.description,
                requirements=info.requirements,
            )

    def _resolve_dependencies(selected):
        planner = DAGPlanner()
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
        return planner.plan(
            selected, RegistrySnapshot(modules=modules)
        ).deterministic_order

    pipeline.resolve_dependencies = _resolve_dependencies

    cfg = TranscriptXConfig()
    cfg.llm.enabled = False
    cfg.llm.provider = "null"

    with patch("transcriptx.core.utils.config.get_config", return_value=cfg):
        review = compute_review_before_run_for_pipeline(
            pipeline,
            transcript_path=str(tmp_path / "mini.json"),
            selected_modules=["narrative_summary"],
            output_dir=str(tmp_path / "out"),
        )

    skipped = {row["module"]: row["reason"] for row in review["modules_skipped"]}
    assert skipped.get("narrative_summary") == "LLM disabled"
    assert "narrative_summary" not in review["modules_will_run"]


@pytest.mark.unit
def test_execute_single_module_fails_on_llm_registry_corruption() -> None:
    from transcriptx.core.llm.errors import LLM_CONFIGURATION_ERROR
    from transcriptx.core.pipeline.dag_execution_adapter import execute_single_module
    from transcriptx.core.pipeline.module_registry import get_module_info

    pipeline = SimpleNamespace(logger=MagicMock())
    info = get_module_info("llm_summary")
    assert info is not None
    node = SimpleNamespace(
        function=MagicMock(),
        description=info.description,
        requirements=info.requirements,
    )
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    with (
        patch(
            "transcriptx.core.pipeline.module_registry.get_module_info",
            side_effect=RuntimeError("registry corrupt"),
        ),
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
    ):
        outcome = execute_single_module(
            pipeline,
            module_name="llm_summary",
            node=node,
            transcript_path="t.json",
            context=None,
            requirements_resolver=None,
            named_speaker_count=2,
        )

    assert outcome.status == "failed"
    assert outcome.module_result is not None
    assert outcome.module_result["error"]["error_code"] == LLM_CONFIGURATION_ERROR
    assert outcome.skip_reason is None


@pytest.mark.unit
def test_execute_single_module_registry_exception_non_llm_fail_open() -> None:
    from transcriptx.core.pipeline.dag_execution_adapter import execute_single_module

    class _OkModule:
        def run_from_context(self, context):
            return {"status": "success", "artifacts": []}

    pipeline = SimpleNamespace(
        logger=MagicMock(),
        _module_progress_heartbeat=lambda *_a, **_k: None,
    )
    node = SimpleNamespace(
        function=_OkModule,
        description="Stats",
        requirements=[],
    )
    cfg = TranscriptXConfig()

    with (
        patch(
            "transcriptx.core.pipeline.dag_pipeline_run.evaluate_llm_gate",
            return_value=("run", None, None),
        ),
        patch(
            "transcriptx.core.pipeline.module_registry.get_module_info",
            side_effect=RuntimeError("registry corrupt"),
        ),
        patch("transcriptx.core.utils.config.get_config", return_value=cfg),
    ):
        outcome = execute_single_module(
            pipeline,
            module_name="stats",
            node=node,
            transcript_path="t.json",
            context=MagicMock(),
            requirements_resolver=None,
            named_speaker_count=2,
        )

    assert outcome.status == "success"


@pytest.mark.unit
def test_review_before_run_surfaces_llm_configuration_error(tmp_path) -> None:
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
    info = registry.get_module_info("llm_summary")
    if info:
        pipeline.nodes["llm_summary"] = SimpleNamespace(
            description=info.description,
            requirements=info.requirements,
        )

    def _resolve_dependencies(selected):
        return ["llm_summary"]

    pipeline.resolve_dependencies = _resolve_dependencies
    cfg = TranscriptXConfig()
    cfg.llm.enabled = True
    cfg.llm.provider = "ollama"

    with patch(
        "transcriptx.core.utils.config.get_config",
        side_effect=RuntimeError("config corrupt"),
    ):
        review = compute_review_before_run_for_pipeline(
            pipeline,
            transcript_path=str(tmp_path / "mini.json"),
            selected_modules=["llm_summary"],
            output_dir=str(tmp_path / "out"),
        )

    skipped = {row["module"]: row["reason"] for row in review["modules_skipped"]}
    assert "llm_summary" in skipped
    assert skipped["llm_summary"].startswith("llm_configuration_error:")
    assert "llm_summary" not in review["modules_will_run"]
