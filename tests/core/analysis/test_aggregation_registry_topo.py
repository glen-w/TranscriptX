"""Unit: production aggregation registry is acyclic and topologically ordered."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.aggregation import aggregators
from transcriptx.core.analysis.aggregation.registry import build_registry
from transcriptx.core.pipeline.group_analysis_runner import _topo_sort_entries


@pytest.mark.unit
def test_build_registry_is_acyclic_and_topologically_valid() -> None:
    registry = build_registry()
    ordered = _topo_sort_entries(registry)
    assert len(ordered) == len(registry)
    assert {entry.agg_id for entry in ordered} == {entry.agg_id for entry in registry}

    position = {entry.agg_id: index for index, entry in enumerate(ordered)}
    known = set(position)
    for entry in registry:
        for dep in entry.deps:
            assert dep in known, f"{entry.agg_id} depends on unknown {dep}"
            assert (
                position[dep] < position[entry.agg_id]
            ), f"{dep} must precede {entry.agg_id}"

    assert position["ner"] < position["entity_sentiment"]
    assert position["highlights"] < position["summary"]
    assert position["pauses"] < position["momentum"]
    assert position["emotion"] < position["contagion"]


@pytest.mark.unit
def test_build_registry_agg_ids_unique_and_output_types_valid() -> None:
    registry = build_registry()
    ids = [entry.agg_id for entry in registry]
    assert len(ids) == len(set(ids))
    for entry in registry:
        assert entry.output_type in {"rows", "blob"}
        assert callable(entry.selector)
        assert callable(entry.aggregate_fn)


@pytest.mark.unit
def test_registry_catalog_uses_aggregator_implementations() -> None:
    """build_registry wires the extracted aggregators module, not copies."""
    import transcriptx.core.analysis.aggregation.registry as registry

    assert registry._aggregate_tics is aggregators._aggregate_tics
    assert registry._aggregate_highlights is aggregators._aggregate_highlights
    assert registry._aggregate_wordclouds is aggregators._aggregate_wordclouds
    by_id = {entry.agg_id: entry.aggregate_fn for entry in build_registry()}
    assert by_id["tics"] is aggregators._aggregate_tics
    assert by_id["highlights"] is aggregators._aggregate_highlights
    assert by_id["wordclouds"] is aggregators._aggregate_wordclouds
