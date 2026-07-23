"""Golden / unit tests for B13 interaction graph export."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.analysis.interactions.graph_export import (
    build_interaction_graph_payload,
    build_network_graph_spec,
    canonical_graph_json_bytes,
    commit_interaction_graph,
    graphml_bytes,
    semantic_graph_from_graphml,
    undirected_chart_edges,
)


def _evt(
    *,
    a: str,
    b: str,
    itype: str,
    a_key: str | None = None,
    b_key: str | None = None,
) -> InteractionEvent:
    return InteractionEvent(
        timestamp=1.0,
        speaker_a=a,
        speaker_b=b,
        interaction_type=itype,
        speaker_a_text="x",
        speaker_b_text="y",
        gap_before=0.1,
        overlap=0.0,
        speaker_a_start=0.0,
        speaker_a_end=1.0,
        speaker_b_start=1.0,
        speaker_b_end=2.0,
        speaker_a_key=a_key if a_key is not None else a,
        speaker_b_key=b_key if b_key is not None else b,
    )


def test_asymmetric_directed_edges_and_keys():
    events = [
        _evt(a="Alice", b="Bob", itype="interruption_gap", a_key="spk_a", b_key="spk_b"),
        _evt(a="Alice", b="Bob", itype="response", a_key="spk_a", b_key="spk_b"),
        _evt(a="Bob", b="Alice", itype="response", a_key="spk_b", b_key="spk_a"),
    ]
    payload = build_interaction_graph_payload(interactions=events)
    assert payload is not None
    assert payload["schema_id"].endswith("interaction_graph.v1")
    ids = {n["id"] for n in payload["nodes"]}
    assert ids == {"spk_a", "spk_b"}
    # interruption: Bob→Alice; responses: Bob→Alice and Alice→Bob
    by = {(e["source"], e["target"]): e for e in payload["edges"]}
    assert by[("spk_b", "spk_a")]["interruptions"] == 1
    assert by[("spk_b", "spk_a")]["responses"] == 1
    assert by[("spk_b", "spk_a")]["weight"] == 2
    assert by[("spk_a", "spk_b")]["responses"] == 1
    assert by[("spk_a", "spk_b")]["interruptions"] == 0


def test_bidirectional_undirected_aggregation():
    events = [
        _evt(a="A", b="B", itype="response", a_key="kA", b_key="kB"),
        _evt(a="B", b="A", itype="response", a_key="kB", b_key="kA"),
    ]
    payload = build_interaction_graph_payload(interactions=events)
    assert payload is not None
    chart_edges = undirected_chart_edges(payload)
    assert len(chart_edges) == 1
    assert chart_edges[0]["weight"] == 2


def test_self_link_dropped():
    events = [
        _evt(a="Alice", b="Alice", itype="response", a_key="same", b_key="same"),
        _evt(a="Alice", b="Bob", itype="response", a_key="same", b_key="other"),
    ]
    payload = build_interaction_graph_payload(interactions=events)
    assert payload is not None
    assert all(e["source"] != e["target"] for e in payload["edges"])


def test_unicode_labels_and_byte_determinism():
    events = [
        _evt(a="Åsa", b="Björn", itype="response", a_key="k1", b_key="k2"),
    ]
    p1 = build_interaction_graph_payload(interactions=events)
    p2 = build_interaction_graph_payload(interactions=events)
    assert p1 is not None and p2 is not None
    b1 = canonical_graph_json_bytes(p1)
    b2 = canonical_graph_json_bytes(p2)
    assert b1 == b2
    assert "Åsa" in b1.decode("utf-8")


def test_missing_equity_nulls_and_degree_sizing():
    events = [_evt(a="A", b="B", itype="response", a_key="kA", b_key="kB")]
    payload = build_interaction_graph_payload(interactions=events, equity={})
    assert payload is not None
    for n in payload["nodes"]:
        assert n["floor_share"] is None
        assert n["interruption_asymmetry"] is None
    spec = build_network_graph_spec(payload, base_name="t")
    assert spec is not None
    assert all(n["size"] >= 20 for n in spec.nodes)


def test_empty_payload_none():
    assert build_interaction_graph_payload(interactions=[]) is None


def test_graphml_semantic_matches_json():
    events = [
        _evt(a="Alice", b="Bob", itype="interruption_gap", a_key="a", b_key="b"),
        _evt(a="Bob", b="Carol", itype="response", a_key="b", b_key="c"),
    ]
    payload = build_interaction_graph_payload(
        interactions=events,
        equity={"floor_share": {"Alice": 0.5, "Bob": 0.3}},
        display_to_key={"Alice": "a", "Bob": "b", "Carol": "c"},
    )
    assert payload is not None
    gml = graphml_bytes(payload)
    sem = semantic_graph_from_graphml(gml)
    json_edges = [
        {
            "source": e["source"],
            "target": e["target"],
            "interruptions": e["interruptions"],
            "responses": e["responses"],
            "weight": e["weight"],
        }
        for e in payload["edges"]
    ]
    assert sem["edges"] == json_edges
    assert {n["id"] for n in sem["nodes"]} == {n["id"] for n in payload["nodes"]}


def test_stale_artifact_cleanup_on_empty(tmp_path: Path):
    class FakeOS:
        base_name = "meeting"
        output_structure = MagicMock()
        output_structure.global_data_dir = tmp_path / "data"
        output_structure.global_static_charts_dir = tmp_path / "static"
        output_structure.global_dynamic_charts_dir = tmp_path / "dynamic"
        removed: list[Path] = []

        def write_artifact_bytes(self, path, data, *, artifact_type="bin"):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(data)

        def save_chart(self, spec, chart_type=None):
            return {"static": None, "dynamic": None}

        def remove_artifacts(self, paths):
            for p in paths:
                path = Path(p)
                self.removed.append(path)
                if path.exists():
                    path.unlink()

    svc = FakeOS()
    data_dir = svc.output_structure.global_data_dir
    data_dir.mkdir(parents=True)
    stale = data_dir / "meeting_interaction_graph.json"
    stale.write_text("{}")

    events = [_evt(a="A", b="B", itype="response", a_key="a", b_key="b")]
    assert commit_interaction_graph(
        interactions=events, analysis_results={}, output_service=svc
    )
    assert stale.exists()

    # Empty rerun clears
    result = commit_interaction_graph(
        interactions=[], analysis_results={}, output_service=svc
    )
    assert result is None
    assert not stale.exists()


def test_isolated_nodes_alone_do_not_keep_graph():
    # Labels without edges → empty
    events = [
        _evt(a="A", b="A", itype="response", a_key="solo", b_key="solo"),
    ]
    assert build_interaction_graph_payload(interactions=events) is None
