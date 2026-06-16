"""Network graph matplotlib renderer.

This renderer is intentionally undirected. Directional semantics must be
normalized upstream before building the spec.
"""

from __future__ import annotations

from typing import Any

from transcriptx.core.viz.mpl.common import apply_axis_labels, draw_no_signal_overlay
from transcriptx.core.viz.mpl.contracts import (
    RenderContractError,
    resolve_no_signal_message,
)
from transcriptx.core.viz.mpl.dispatch import register
from transcriptx.core.viz.mpl.empty_signal import (
    any_nonzero,
    coerce_floats,
    register_probe,
)
from transcriptx.core.viz.specs import NetworkGraphSpec


@register_probe(NetworkGraphSpec)
def network_has_signal(spec: NetworkGraphSpec) -> bool:
    weights = coerce_floats(edge.get("weight", 0) for edge in spec.edges)
    return bool(weights) and any_nonzero(weights)


@register(NetworkGraphSpec)
def render_network(spec: NetworkGraphSpec, plt: Any) -> Any:
    import networkx as nx

    node_ids: list[str] = []
    labels: dict[str, str] = {}
    node_sizes: list[float] = []
    node_colors: list[str] = []

    for node in spec.nodes:
        node_id = node.get("id")
        if not node_id:
            raise RenderContractError(
                "Network graph contract violation: every node must define a non-empty 'id'."
            )
        node_key = str(node_id)
        node_ids.append(node_key)
        labels[node_key] = str(node.get("label", node_key))
        node_colors.append(str(node.get("color", "lightblue")))
        node_sizes.append(float(node.get("size", 0)))

    node_id_set = set(node_ids)
    for edge in spec.edges:
        source = str(edge["source"])
        target = str(edge["target"])
        if source not in node_id_set or target not in node_id_set:
            raise RenderContractError(
                "Network graph contract violation: edge endpoints must match node ids."
            )

    graph = nx.Graph()
    for node_id in node_ids:
        graph.add_node(node_id)
    for edge in spec.edges:
        graph.add_edge(
            str(edge["source"]),
            str(edge["target"]),
            weight=edge.get("weight", 1),
        )

    if graph.number_of_nodes() == 0:
        raise ValueError("Network graph must have at least one node")

    fig, ax = plt.subplots(figsize=(12, 10))
    positions = spec.node_positions
    if not positions or any(node_id not in positions for node_id in graph.nodes):
        positions = nx.spring_layout(graph, k=1, iterations=50)

    edges = list(graph.edges())
    weights = [
        graph[u][v].get("weight", 1) if "weight" in graph[u][v] else 1 for u, v in edges
    ]
    nx.draw_networkx_edges(
        graph,
        positions,
        edgelist=edges,
        width=[w / 2 for w in weights],
        alpha=0.7,
        ax=ax,
    )

    computed_sizes: list[float] = []
    for idx, node_id in enumerate(node_ids):
        explicit_size = node_sizes[idx]
        if explicit_size > 0:
            computed_sizes.append(explicit_size)
        else:
            computed_sizes.append(graph.degree(node_id) * 200 + 500)

    nx.draw_networkx_nodes(
        graph,
        positions,
        node_color=node_colors,
        node_size=computed_sizes,
        alpha=0.8,
        ax=ax,
    )
    nx.draw_networkx_labels(
        graph, positions, labels, font_size=10, font_weight="bold", ax=ax
    )

    edge_labels: dict[tuple[str, str], str] = {}
    for edge in spec.edges:
        source = str(edge["source"])
        target = str(edge["target"])
        weight = float(edge.get("weight", 1))
        if weight > 0:
            edge_labels[(source, target)] = str(edge.get("label", f"res:{int(weight)}"))
    nx.draw_networkx_edge_labels(
        graph, positions, edge_labels=edge_labels, font_size=8, ax=ax
    )

    apply_axis_labels(ax, spec)
    ax.axis("off")
    draw_no_signal_overlay(ax, resolve_no_signal_message(spec))
    fig.tight_layout()
    return fig
