"""B13 interaction graph builder and artifact commit (JSON + GraphML + chart)."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping

import networkx as nx

from transcriptx.core.analysis.interactions.events import InteractionEvent
from transcriptx.core.analysis.interactions.roles import resolve_interaction_roles
from transcriptx.core.utils.output_standards import (
    get_global_dynamic_chart_path,
    get_global_static_chart_path,
)
from transcriptx.core.viz.specs import NetworkGraphSpec
from transcriptx.utils.text_utils import is_named_speaker

SCHEMA_ID = "transcriptx.interactions.interaction_graph.v1"
SCHEMA_VERSION = 1
BUILDER_VERSION = 1
GRAPH_DATA_FILENAME = "interaction_graph"
NETWORK_CHART_NAME = "network_graph"
NETWORK_CHART_TYPE = "network"
LAYOUT_SEED = 42

_SIZE_MIN = 20
_SIZE_MAX = 100
_SIZE_SHARE_LO = 24
_SIZE_SHARE_HI = 96


def _as_finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if hasattr(value, "item"):
            value = value.item()
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num):
        return None
    return num


def _as_nonneg_int(value: Any) -> int:
    num = _as_finite_float(value)
    if num is None:
        return 0
    return max(0, int(num))


def _event_keys(event: InteractionEvent) -> tuple[str, str] | None:
    a_key = (getattr(event, "speaker_a_key", None) or "").strip()
    b_key = (getattr(event, "speaker_b_key", None) or "").strip()
    a_label = (event.speaker_a or "").strip()
    b_label = (event.speaker_b or "").strip()
    if not a_label or not b_label:
        return None
    if not is_named_speaker(a_label) or not is_named_speaker(b_label):
        return None
    # Prefer immutable keys; fall back to labels only when keys absent (legacy events).
    return (a_key or a_label, b_key or b_label)


def build_directed_counts(
    interactions: list[InteractionEvent],
) -> tuple[
    dict[str, dict[str, dict[str, int]]],
    dict[str, str],
]:
    """Return counts[actor][target][{interruptions,responses}] and labels[id]."""
    counts: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"interruptions": 0, "responses": 0})
    )
    labels: dict[str, str] = {}

    for event in interactions:
        keys = _event_keys(event)
        if keys is None:
            continue
        a_key, b_key = keys
        labels.setdefault(a_key, (event.speaker_a or a_key).strip() or a_key)
        labels.setdefault(b_key, (event.speaker_b or b_key).strip() or b_key)

        roles = resolve_interaction_roles(event)
        if roles is None:
            continue

        # Remap actor/target display names to keys via event field positions.
        if roles.actor == event.speaker_b:
            actor_key, target_key = b_key, a_key
        elif roles.actor == event.speaker_a:
            actor_key, target_key = a_key, b_key
        else:
            continue

        if actor_key == target_key:
            continue

        bucket = counts[actor_key][target_key]
        if roles.matrix_key == "interruptions":
            bucket["interruptions"] += 1
        elif roles.matrix_key == "responses":
            bucket["responses"] += 1

    plain: dict[str, dict[str, dict[str, int]]] = {}
    for actor, targets in counts.items():
        plain[actor] = {
            target: {
                "interruptions": int(vals["interruptions"]),
                "responses": int(vals["responses"]),
            }
            for target, vals in targets.items()
            if int(vals["interruptions"]) > 0 or int(vals["responses"]) > 0
        }
    return plain, labels


def _remap_by_key(
    display_map: Mapping[str, Any] | None,
    display_to_key: Mapping[str, str],
) -> dict[str, Any]:
    if not display_map:
        return {}
    out: dict[str, Any] = {}
    for display, value in display_map.items():
        key = display_to_key.get(str(display))
        if key is None:
            key = str(display)
        out[key] = value
    return out


def build_interaction_graph_payload(
    *,
    interactions: list[InteractionEvent],
    equity: Mapping[str, Any] | None = None,
    dominance_scores: Mapping[str, Any] | None = None,
    display_to_key: Mapping[str, str] | None = None,
    semantics_version: int = 2,
) -> dict[str, Any] | None:
    """Build canonical JSON payload, or None when empty (no edges)."""
    counts, labels = build_directed_counts(interactions)
    display_to_key = dict(display_to_key or {})
    for key, label in labels.items():
        display_to_key.setdefault(label, key)

    equity = equity or {}
    floor_share = _remap_by_key(equity.get("floor_share"), display_to_key)
    asymmetry = _remap_by_key(equity.get("interruption_asymmetry"), display_to_key)
    dominance = _remap_by_key(dominance_scores, display_to_key)

    edges: list[dict[str, Any]] = []
    degree: dict[str, int] = defaultdict(int)
    node_ids: set[str] = set(labels.keys())

    for actor, targets in counts.items():
        node_ids.add(actor)
        for target, vals in targets.items():
            node_ids.add(target)
            interruptions = _as_nonneg_int(vals.get("interruptions", 0))
            responses = _as_nonneg_int(vals.get("responses", 0))
            weight = interruptions + responses
            if weight <= 0 or actor == target:
                continue
            edges.append(
                {
                    "source": actor,
                    "target": target,
                    "interruptions": interruptions,
                    "responses": responses,
                    "weight": weight,
                }
            )
            degree[actor] += weight
            degree[target] += weight

    if not edges:
        return None

    nodes: list[dict[str, Any]] = []
    for node_id in sorted(node_ids):
        nodes.append(
            {
                "id": node_id,
                "label": labels.get(node_id) or node_id,
                "degree_total": int(degree.get(node_id, 0)),
                "floor_share": _as_finite_float(floor_share.get(node_id)),
                "interruption_asymmetry": _as_finite_float(asymmetry.get(node_id)),
                "dominance_score": _as_finite_float(dominance.get(node_id)),
            }
        )

    edges.sort(key=lambda e: (e["source"], e["target"]))

    return {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "semantics_version": int(semantics_version),
        "module": "interactions",
        "scope": "global",
        "directed": True,
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "node_id_kind": "grouping_key",
            "edge_weight_unit": "event_count",
            "builder_version": BUILDER_VERSION,
        },
    }


def canonical_graph_json_bytes(payload: Mapping[str, Any]) -> bytes:
    text = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return (text + "\n").encode("utf-8")


def payload_to_digraph(payload: Mapping[str, Any]) -> nx.DiGraph:
    g = nx.DiGraph()
    for node in payload.get("nodes") or []:
        nid = str(node["id"])
        attrs: dict[str, Any] = {"label": str(node.get("label") or nid)}
        for key in (
            "degree_total",
            "floor_share",
            "interruption_asymmetry",
            "dominance_score",
        ):
            val = node.get(key)
            if val is None:
                continue
            if key == "degree_total":
                attrs[key] = int(val)
            else:
                f = _as_finite_float(val)
                if f is not None:
                    attrs[key] = f
        g.add_node(nid, **attrs)
    for edge in payload.get("edges") or []:
        src, tgt = str(edge["source"]), str(edge["target"])
        if src == tgt:
            continue
        g.add_edge(
            src,
            tgt,
            interruptions=int(edge.get("interruptions", 0)),
            responses=int(edge.get("responses", 0)),
            weight=int(edge.get("weight", 0)),
        )
    return g


def graphml_bytes(payload: Mapping[str, Any]) -> bytes:
    g = payload_to_digraph(payload)
    bio = BytesIO()
    nx.write_graphml(g, bio, encoding="utf-8", prettyprint=True)
    return bio.getvalue()


def undirected_chart_edges(
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    weights: dict[tuple[str, str], int] = defaultdict(int)
    for edge in payload.get("edges") or []:
        a, b = str(edge["source"]), str(edge["target"])
        if a == b:
            continue
        pair = tuple(sorted((a, b)))
        weights[pair] += int(edge.get("weight", 0))
    out = []
    for (a, b), w in sorted(weights.items()):
        if w <= 0:
            continue
        out.append({"source": a, "target": b, "weight": w, "label": f"w:{w}"})
    return out


def node_chart_sizes(payload: Mapping[str, Any]) -> dict[str, float]:
    nodes = list(payload.get("nodes") or [])
    shares = [
        _as_finite_float(n.get("floor_share"))
        for n in nodes
        if _as_finite_float(n.get("floor_share")) is not None
    ]
    use_share = len(shares) > 0 and len(set(shares)) > 1
    sizes: dict[str, float] = {}
    if use_share:
        lo, hi = min(shares), max(shares)
        span = hi - lo if hi > lo else 1.0
        for n in nodes:
            nid = str(n["id"])
            fs = _as_finite_float(n.get("floor_share"))
            if fs is None:
                deg = int(n.get("degree_total") or 0)
                sizes[nid] = float(max(_SIZE_MIN, min(_SIZE_MAX, 20 + 5 * deg)))
            else:
                t = (fs - lo) / span
                sizes[nid] = _SIZE_SHARE_LO + t * (_SIZE_SHARE_HI - _SIZE_SHARE_LO)
        return sizes
    for n in nodes:
        nid = str(n["id"])
        deg = int(n.get("degree_total") or 0)
        sizes[nid] = float(max(_SIZE_MIN, min(_SIZE_MAX, 20 + 5 * deg)))
    return sizes


def build_network_graph_spec(
    payload: Mapping[str, Any], *, base_name: str
) -> NetworkGraphSpec | None:
    chart_edges = undirected_chart_edges(payload)
    if not chart_edges:
        return None
    sizes = node_chart_sizes(payload)
    nodes_sorted = sorted(payload.get("nodes") or [], key=lambda n: str(n["id"]))
    nodes = [
        {
            "id": str(n["id"]),
            "label": str(n.get("label") or n["id"]),
            "size": sizes.get(str(n["id"]), float(_SIZE_MIN)),
        }
        for n in nodes_sorted
    ]
    g = nx.Graph()
    for n in nodes:
        g.add_node(n["id"])
    for e in chart_edges:
        g.add_edge(e["source"], e["target"], weight=e["weight"])
    pos = nx.spring_layout(g, seed=LAYOUT_SEED, weight="weight")
    node_positions = {
        nid: (float(xy[0]), float(xy[1])) for nid, xy in sorted(pos.items())
    }
    return NetworkGraphSpec(
        viz_id="interactions.network_graph.global",
        module="interactions",
        name=NETWORK_CHART_NAME,
        scope="global",
        chart_intent="network_graph",
        title=f"Speaker Interaction Network - {base_name}",
        nodes=nodes,
        edges=chart_edges,
        node_positions=node_positions,
    )


def interaction_graph_artifact_paths(output_service: Any) -> dict[str, Path | None]:
    """Resolve known artifact Paths for commit/remove."""
    base = output_service.base_name
    data_dir = output_service.output_structure.global_data_dir
    json_path = data_dir / f"{base}_{GRAPH_DATA_FILENAME}.json"
    graphml_path = data_dir / f"{base}_{GRAPH_DATA_FILENAME}.graphml"
    static_path = get_global_static_chart_path(
        output_service.output_structure, None, NETWORK_CHART_NAME, NETWORK_CHART_TYPE
    )
    dynamic_path = get_global_dynamic_chart_path(
        output_service.output_structure, None, NETWORK_CHART_NAME, NETWORK_CHART_TYPE
    )
    evidence_path = Path(static_path).with_suffix(".evidence.json")
    return {
        "json": json_path,
        "graphml": graphml_path,
        "static": Path(static_path),
        "dynamic": Path(dynamic_path),
        "evidence": evidence_path,
    }


def remove_interaction_graph_artifacts(output_service: Any) -> None:
    """Delete prior graph JSON/GraphML/chart/evidence (empty-result policy)."""
    paths = interaction_graph_artifact_paths(output_service)
    output_service.remove_artifacts([p for p in paths.values() if p is not None])


def commit_interaction_graph(
    *,
    interactions: list[InteractionEvent],
    analysis_results: Mapping[str, Any],
    output_service: Any,
) -> dict[str, Any] | None:
    """Build, write or clear graph artifacts; return payload or None if empty."""
    equity = analysis_results.get("equity") or {}
    dominance = analysis_results.get("dominance_scores") or {}
    display_to_key = dict(analysis_results.get("speaker_key_map") or {})

    payload = build_interaction_graph_payload(
        interactions=interactions,
        equity=equity,
        dominance_scores=dominance,
        display_to_key=display_to_key,
        semantics_version=int(
            analysis_results.get("semantics_version")
            or analysis_results.get("summary", {}).get("semantics_version")
            or 2
        ),
    )
    if payload is None:
        remove_interaction_graph_artifacts(output_service)
        return None

    paths = interaction_graph_artifact_paths(output_service)
    assert paths["json"] is not None and paths["graphml"] is not None
    paths["json"].parent.mkdir(parents=True, exist_ok=True)
    output_service.write_artifact_bytes(
        paths["json"], canonical_graph_json_bytes(payload), artifact_type="json"
    )
    output_service.write_artifact_bytes(
        paths["graphml"], graphml_bytes(payload), artifact_type="graphml"
    )

    spec = build_network_graph_spec(payload, base_name=output_service.base_name)
    if spec is None:
        remove_interaction_graph_artifacts(output_service)
        return None
    output_service.save_chart(spec, chart_type=NETWORK_CHART_TYPE)
    return payload


def semantic_graph_from_graphml(data: bytes) -> dict[str, Any]:
    """Parse GraphML to a comparable semantic dict (for tests)."""
    g = nx.read_graphml(BytesIO(data))
    nodes = []
    for nid, attrs in sorted(g.nodes(data=True), key=lambda t: str(t[0])):
        entry: dict[str, Any] = {"id": str(nid), "label": str(attrs.get("label", nid))}
        for key in (
            "degree_total",
            "floor_share",
            "interruption_asymmetry",
            "dominance_score",
        ):
            if key not in attrs:
                continue
            if key == "degree_total":
                entry[key] = int(float(attrs[key]))
            else:
                entry[key] = _as_finite_float(attrs[key])
        nodes.append(entry)
    edges = []
    for u, v, attrs in sorted(g.edges(data=True), key=lambda t: (str(t[0]), str(t[1]))):
        edges.append(
            {
                "source": str(u),
                "target": str(v),
                "interruptions": int(float(attrs.get("interruptions", 0))),
                "responses": int(float(attrs.get("responses", 0))),
                "weight": int(float(attrs.get("weight", 0))),
            }
        )
    return {"nodes": nodes, "edges": edges}
