"""Matplotlib rendering for chart specs."""

from __future__ import annotations

from typing import Any

import numpy as np

from transcriptx.core.utils.lazy_imports import get_matplotlib_pyplot
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    BoxSpec,
    ChartSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
    NetworkGraphSpec,
    ScatterSpec,
)


def render_mpl(spec: ChartSpec) -> Any:
    """Render a matplotlib figure from a ChartSpec."""
    spec.validate()
    plt = get_matplotlib_pyplot()

    def _scatter_kwargs(marker: dict[str, Any] | None) -> dict[str, Any]:
        if not marker:
            return {}
        kwargs: dict[str, Any] = {}
        color = marker.get("color")
        if color is not None:
            kwargs["c"] = color
        size = marker.get("size")
        if size is not None:
            kwargs["s"] = size
        opacity = marker.get("opacity")
        if opacity is not None and not isinstance(opacity, list):
            kwargs["alpha"] = opacity
        symbol = marker.get("symbol")
        if isinstance(symbol, str):
            kwargs["marker"] = symbol
        return kwargs

    if isinstance(spec, LineTimeSeriesSpec) or spec.chart_intent == "line_timeseries":
        fig, ax = plt.subplots(figsize=(10, 4))
        for series in spec.series:
            name = series.get("name", "")
            x_vals = series.get("x", [])
            y_vals = series.get("y", [])
            if spec.markers:
                ax.plot(x_vals, y_vals, marker="o", label=name)
            else:
                ax.plot(x_vals, y_vals, label=name)
        ax.set_title(spec.title)
        if spec.x_label:
            ax.set_xlabel(spec.x_label)
        if spec.y_label:
            ax.set_ylabel(spec.y_label)
        if any(series.get("name") for series in spec.series):
            ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return fig

    if isinstance(spec, ScatterSpec) or spec.chart_intent in (
        "scatter",
        "scatter_events",
    ):
        fig, ax = plt.subplots(figsize=(10, 4))
        series_list = spec.get_series()
        for series in series_list:
            marker = series.marker or {}
            scatter_kwargs = _scatter_kwargs(marker)
            if spec.mode in ("markers", "lines+markers"):
                ax.scatter(
                    series.x, series.y, label=series.name or None, **scatter_kwargs
                )
            if spec.mode in ("lines", "lines+markers"):
                line_kwargs: dict[str, Any] = {}
                color = marker.get("color")
                if isinstance(color, str):
                    line_kwargs["color"] = color
                ax.plot(series.x, series.y, **line_kwargs)
        ax.set_title(spec.title)
        if spec.x_label:
            ax.set_xlabel(spec.x_label)
        if spec.y_label:
            ax.set_ylabel(spec.y_label)
        if any(series.name for series in series_list):
            ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        return fig

    if isinstance(spec, HeatmapMatrixSpec) or spec.chart_intent == "heatmap_matrix":
        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(spec.z, vmin=spec.zmin, vmax=spec.zmax, aspect="auto")
        ax.set_title(spec.title)
        if spec.x_label:
            ax.set_xlabel(spec.x_label)
        if spec.y_label:
            ax.set_ylabel(spec.y_label)
        ax.set_xticks(range(len(spec.x_labels)))
        ax.set_xticklabels(spec.x_labels, rotation=45, ha="right")
        ax.set_yticks(range(len(spec.y_labels)))
        ax.set_yticklabels(spec.y_labels)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        return fig

    if isinstance(spec, BarCategoricalSpec) or spec.chart_intent == "bar_categorical":
        fig, ax = plt.subplots(figsize=(8, 4))
        if spec.series:
            width = 0.8 / max(1, len(spec.series))
            for idx, series in enumerate(spec.series):
                categories = series.get("categories", spec.categories)
                values = series.get("values", [])
                positions = [i + idx * width for i in range(len(categories))]
                if spec.orientation == "horizontal":
                    ax.barh(positions, values, height=width, label=series.get("name"))
                else:
                    ax.bar(positions, values, width=width, label=series.get("name"))
            if any(series.get("name") for series in spec.series):
                ax.legend()
            if spec.orientation == "horizontal":
                ax.set_yticks([i + width for i in range(len(spec.categories))])
                ax.set_yticklabels(spec.categories)
            else:
                ax.set_xticks([i + width for i in range(len(spec.categories))])
                ax.set_xticklabels(spec.categories, rotation=30, ha="right")
        else:
            if spec.orientation == "horizontal":
                ax.barh(spec.categories, spec.values)
            else:
                ax.bar(spec.categories, spec.values)
                ax.set_xticks(range(len(spec.categories)))
                ax.set_xticklabels(spec.categories, rotation=30, ha="right")
        ax.set_title(spec.title)
        if spec.x_label:
            ax.set_xlabel(spec.x_label)
        if spec.y_label:
            ax.set_ylabel(spec.y_label)
        fig.tight_layout()
        return fig

    if isinstance(spec, BoxSpec) or spec.chart_intent == "box_plot":
        fig, ax = plt.subplots(figsize=(10, 4))
        series_list = list(spec.series)
        if not series_list:
            raise ValueError("BoxSpec requires at least one series")

        # Collect categories from series x-values
        categories: list[str] = []
        for series in series_list:
            xs = [str(x) for x in series.get("x", [])]
            for x in xs:
                if x not in categories:
                    categories.append(x)

        if not categories:
            # If x not provided, fall back to per-series boxes
            categories = [
                series.get("name", f"series_{idx}")
                for idx, series in enumerate(series_list)
            ]

        base_positions = list(range(len(categories)))
        width = 0.8 / max(1, len(series_list))

        for idx, series in enumerate(series_list):
            xs = [str(x) for x in series.get("x", [])]
            ys = series.get("y", [])
            # Group y values by category
            grouped: list[list[float]] = [[] for _ in categories]
            if xs:
                for x_val, y_val in zip(xs, ys):
                    if x_val in categories:
                        grouped[categories.index(x_val)].append(y_val)
            else:
                # If no x-values, treat all ys as one group
                grouped = [list(ys)]

            filtered = [(cat, vals) for cat, vals in zip(categories, grouped) if vals]
            if not filtered:
                continue
            positions = [
                base_positions[categories.index(cat)]
                + (idx - (len(series_list) - 1) / 2) * width
                for cat, _ in filtered
            ]
            ax.boxplot(
                [vals for _, vals in filtered],
                positions=positions,
                widths=width * 0.9,
                patch_artist=True,
                showfliers=True,
            )
            if spec.show_points:
                for pos, (_, vals) in zip(positions, filtered):
                    jitter = (np.random.rand(len(vals)) - 0.5) * width * 0.6
                    ax.scatter(
                        [pos + j for j in jitter],
                        vals,
                        alpha=0.6,
                        s=10,
                    )

        ax.set_title(spec.title)
        if spec.x_label:
            ax.set_xlabel(spec.x_label)
        if spec.y_label:
            ax.set_ylabel(spec.y_label)
        ax.set_xticks(base_positions)
        ax.set_xticklabels(categories, rotation=30, ha="right")
        fig.tight_layout()
        return fig

    if isinstance(spec, NetworkGraphSpec) or spec.chart_intent == "network_graph":
        import networkx as nx

        # Create networkx graph
        G = nx.Graph()
        for node in spec.nodes:
            G.add_node(node.get("id", node.get("label")))
        for edge in spec.edges:
            G.add_edge(edge["source"], edge["target"], weight=edge.get("weight", 1))

        if G.number_of_nodes() == 0:
            raise ValueError("Network graph must have at least one node")

        fig, ax = plt.subplots(figsize=(12, 10))

        # Calculate layout
        pos = spec.node_positions
        if not pos:
            pos = nx.spring_layout(G, k=1, iterations=50)

        # Draw edges
        edges = list(G.edges())
        weights = [
            G[u][v].get("weight", 1) if "weight" in G[u][v] else 1 for u, v in edges
        ]
        nx.draw_networkx_edges(
            G, pos, edgelist=edges, width=[w / 2 for w in weights], alpha=0.7, ax=ax
        )

        # Draw nodes
        node_sizes = [
            node.get("size", G.degree(node.get("id", node.get("label"))) * 200 + 500)
            for node in spec.nodes
        ]
        node_colors = [node.get("color", "lightblue") for node in spec.nodes]
        nx.draw_networkx_nodes(
            G, pos, node_color=node_colors, node_size=node_sizes, alpha=0.8, ax=ax
        )

        # Draw labels
        labels = {
            node.get("id", node.get("label")): node.get("label", node.get("id", ""))
            for node in spec.nodes
        }
        nx.draw_networkx_labels(G, pos, labels, font_size=10, font_weight="bold", ax=ax)

        # Draw edge labels - use edge data from spec instead of graph
        edge_labels = {}
        for edge in spec.edges:
            source = edge["source"]
            target = edge["target"]
            weight = edge.get("weight", 1)
            if weight > 0:
                label = edge.get("label", f"res:{int(weight)}")
                edge_labels[(source, target)] = label
        nx.draw_networkx_edge_labels(
            G, pos, edge_labels=edge_labels, font_size=8, ax=ax
        )

        ax.set_title(spec.title)
        ax.axis("off")
        fig.tight_layout()
        return fig

    raise ValueError(f"Unsupported chart_intent: {spec.chart_intent}")
