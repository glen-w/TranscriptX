from __future__ import annotations

from unittest.mock import MagicMock

from transcriptx.core.pipeline.dag_pipeline import DAGPipeline
from transcriptx.core.pipeline.dag_planner import DAGPlanner


def _sample_pipeline() -> DAGPipeline:
    pipeline = DAGPipeline()
    pipeline.add_module("base", "Base", "heavy", [], MagicMock())
    pipeline.add_module("light_dep", "Light", "light", ["base"], MagicMock())
    pipeline.add_module("medium_peer", "Medium", "medium", ["base"], MagicMock())
    pipeline.add_module("contagion", "Contagion", "medium", [], MagicMock())
    pipeline.add_module("emotion", "Emotion", "light", [], MagicMock())
    return pipeline


def test_planner_topological_order_matches_pipeline_public_delegate() -> None:
    pipeline = _sample_pipeline()
    planner = DAGPlanner()
    modules = ["base", "light_dep", "medium_peer"]

    assert pipeline.topological_sort(modules) == planner.topological_sort(
        modules, pipeline._registry_snapshot()
    )


def test_planner_implicit_dependency_parity_with_pipeline_delegate() -> None:
    pipeline = _sample_pipeline()
    planner = DAGPlanner()

    for module_name in pipeline.nodes:
        assert pipeline.check_implicit_dependencies(
            module_name
        ) == planner.check_implicit_dependencies(module_name)


def test_planner_category_sort_is_deterministic_and_matches_delegate() -> None:
    pipeline = _sample_pipeline()
    planner = DAGPlanner()
    modules = ["medium_peer", "light_dep", "base"]

    first = planner.sort_by_category(modules, pipeline._registry_snapshot())
    second = planner.sort_by_category(modules, pipeline._registry_snapshot())

    assert first == second
    assert first == pipeline.sort_by_category(modules)
    assert first.index("base") < first.index("light_dep")
