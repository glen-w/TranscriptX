"""
Config matrix tests for module selection and dependency resolution.
"""

from unittest.mock import MagicMock

import pytest

from transcriptx.core.pipeline.dag_pipeline import DAGPipeline
from transcriptx.core.pipeline.module_registry import get_module_info


def _build_pipeline(module_names):
    pipeline = DAGPipeline()
    for module_name in module_names:
        info = get_module_info(module_name)
        assert info is not None
        pipeline.add_module(
            name=module_name,
            description=info.description,
            category=info.category,
            dependencies=info.dependencies,
            function=MagicMock(),
        )
    return pipeline


@pytest.mark.unit
@pytest.mark.parametrize(
    "requested,expected_includes,ordering_checks",
    [
        (["stats"], {"stats"}, []),
        (["contagion"], {"emotion", "contagion"}, [("emotion", "contagion")]),
        (
            ["entity_sentiment"],
            {"entity_sentiment", "ner", "sentiment"},
            [("ner", "entity_sentiment"), ("sentiment", "entity_sentiment")],
        ),
        (["qa_analysis"], {"acts", "qa_analysis"}, [("acts", "qa_analysis")]),
        (["sentiment", "stats"], {"sentiment", "stats"}, [("stats", "sentiment")]),
    ],
)
def test_dependency_resolution_config_matrix(
    requested, expected_includes, ordering_checks
):
    """Ensure module selection honors dependencies across config variants."""
    pipeline = _build_pipeline(expected_includes)
    execution_order = pipeline.resolve_dependencies(requested)

    assert expected_includes.issubset(set(execution_order))
    for before, after in ordering_checks:
        assert execution_order.index(before) < execution_order.index(after)
