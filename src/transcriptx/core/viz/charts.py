"""
Chart saving utilities for static (matplotlib) and dynamic (plotly) outputs.

This module centralizes Plotly availability checks and warning-once behavior.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from transcriptx.core.utils.lazy_imports import optional_import
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.viz.specs import (
    BarCategoricalSpec,
    BoxSpec,
    ChartSpec,
    HeatmapMatrixSpec,
    LineTimeSeriesSpec,
    NetworkGraphSpec,
    ScatterSpec,
)

logger = get_logger()

_plotly_available: Optional[bool] = None
_warned_missing_plotly: bool = False


def is_plotly_available() -> bool:
    """Check if Plotly is available (cached)."""
    global _plotly_available
    if _plotly_available is not None:
        return _plotly_available
    try:
        optional_import("plotly.graph_objects", "interactive charts", "plotly")
        _plotly_available = True
    except ImportError:
        _plotly_available = False
    return _plotly_available


def _warn_missing_plotly_once(warned_state: Optional[dict[str, bool]] = None) -> None:
    global _warned_missing_plotly
    if warned_state is not None:
        if warned_state.get("warned_plotly_missing"):
            return
        warned_state["warned_plotly_missing"] = True
    else:
        if _warned_missing_plotly:
            return
        _warned_missing_plotly = True
    logger.warning(
        "Plotly not installed; skipping dynamic charts. Install transcriptx[plotly] to enable."
    )


def warn_missing_plotly_once(warned_state: Optional[dict[str, bool]] = None) -> None:
    """Public wrapper to warn about missing Plotly exactly once."""
    _warn_missing_plotly_once(warned_state)


def require_plotly() -> None:
    """Require Plotly to be installed; raise if missing."""
    if not is_plotly_available():
        raise RuntimeError(
            "Plotly is required when dynamic_charts='on'. Install transcriptx[plotly]."
        )


def save_static_chart(fig: Any, chart_path: Path, dpi: int = 300) -> Path:
    """Save a matplotlib figure to a resolved path."""
    if chart_path.suffix.lower() != ".png":
        raise ValueError("Static chart paths must end with .png")
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(chart_path), dpi=dpi, bbox_inches="tight")
    return chart_path


def save_dynamic_chart(fig: Any, chart_path: Path) -> Optional[Path]:
    """Save a plotly figure as HTML to a resolved path."""
    if fig is None:
        return None
    if chart_path.suffix.lower() != ".html":
        raise ValueError("Dynamic chart paths must end with .html")
    if not is_plotly_available():
        _warn_missing_plotly_once()
        return None
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    from plotly.io import write_html

    write_html(
        fig,
        file=str(chart_path),
        include_plotlyjs=True,
        full_html=True,
    )
    return chart_path


def render_plotly(spec: ChartSpec) -> Any | None:
    """Render a plotly figure from a ChartSpec."""
    if not is_plotly_available():
        return None
    spec.validate()
    from plotly import graph_objects as go

    def _infer_y_is_categorical(series_list: list[Any], explicit: bool | None) -> bool:
        if explicit is not None:
            return explicit
        for series in series_list:
            if any(isinstance(val, str) for val in series.y):
                return True
        return False

    if isinstance(spec, LineTimeSeriesSpec) or spec.chart_intent == "line_timeseries":
        fig = go.Figure()
        for series in spec.series:
            text = series.get("text")
            fig.add_trace(
                go.Scatter(
                    x=series.get("x", []),
                    y=series.get("y", []),
                    mode="lines+markers" if spec.markers else "lines",
                    name=series.get("name"),
                    text=text,
                    hoverinfo="text" if text else None,
                )
            )
        fig.update_layout(
            title=spec.title,
            xaxis_title=spec.x_label,
            yaxis_title=spec.y_label,
        )
        return fig

    if isinstance(spec, ScatterSpec) or spec.chart_intent in ("scatter", "scatter_events"):
        fig = go.Figure()
        series_list = spec.get_series()
        for series in series_list:
            marker = series.marker or {}
            hoverinfo = "text" if series.text else "skip"
            fig.add_trace(
                go.Scatter(
                    x=series.x,
                    y=series.y,
                    mode=spec.mode,
                    name=series.name,
                    text=series.text,
                    marker=marker,
                    hoverinfo=hoverinfo,
                )
            )
        fig.update_layout(
            title=spec.title,
            xaxis_title=spec.x_label,
            yaxis_title=spec.y_label,
        )
        if _infer_y_is_categorical(series_list, spec.y_is_categorical):
            fig.update_yaxes(type="category")
        return fig

    if isinstance(spec, HeatmapMatrixSpec) or spec.chart_intent == "heatmap_matrix":
        fig = go.Figure(
            data=go.Heatmap(
                z=spec.z,
                x=spec.x_labels,
                y=spec.y_labels,
                zmin=spec.zmin,
                zmax=spec.zmax,
                colorscale="Blues",
            )
        )
        fig.update_layout(
            title=spec.title,
            xaxis_title=spec.x_label,
            yaxis_title=spec.y_label,
        )
        return fig

    if isinstance(spec, BarCategoricalSpec) or spec.chart_intent == "bar_categorical":
        fig = go.Figure()
        if spec.series:
            for series in spec.series:
                categories = series.get("categories", spec.categories)
                values = series.get("values", [])
                fig.add_trace(
                    go.Bar(
                        x=categories if spec.orientation == "vertical" else values,
                        y=values if spec.orientation == "vertical" else categories,
                        name=series.get("name"),
                        orientation="h" if spec.orientation == "horizontal" else "v",
                    )
                )
        else:
            fig.add_trace(
                go.Bar(
                    x=spec.categories if spec.orientation == "vertical" else spec.values,
                    y=spec.values if spec.orientation == "vertical" else spec.categories,
                    orientation="h" if spec.orientation == "horizontal" else "v",
                )
            )
        fig.update_layout(
            title=spec.title,
            xaxis_title=spec.x_label,
            yaxis_title=spec.y_label,
        )
        return fig

    if isinstance(spec, BoxSpec) or spec.chart_intent == "box_plot":
        fig = go.Figure()
        series_list = list(spec.series)
        for series in series_list:
            x_vals = series.get("x", [])
            y_vals = series.get("y", [])
            fig.add_trace(
                go.Box(
                    x=x_vals,
                    y=y_vals,
                    name=series.get("name"),
                    boxpoints="all" if spec.show_points else False,
                    jitter=0.3 if spec.show_points else 0,
                )
            )
        fig.update_layout(
            title=spec.title,
            xaxis_title=spec.x_label,
            yaxis_title=spec.y_label,
            boxmode="group",
        )
        return fig

    if isinstance(spec, NetworkGraphSpec) or spec.chart_intent == "network_graph":
        # Use plotly's network graph capabilities
        # We'll use scatter plots for nodes and lines for edges
        import networkx as nx
        
        # Create networkx graph for layout calculation
        G = nx.Graph()
        for node in spec.nodes:
            G.add_node(node.get("id", node.get("label")))
        for edge in spec.edges:
            G.add_edge(edge["source"], edge["target"], weight=edge.get("weight", 1))
        
        # Calculate layout
        if G.number_of_nodes() == 0:
            return None
        pos = spec.node_positions
        if not pos:
            pos = nx.spring_layout(G, k=1, iterations=50)
        
        # Extract node positions
        node_x = []
        node_y = []
        node_text = []
        node_sizes = []
        node_colors = []
        
        for node in spec.nodes:
            node_id = node.get("id", node.get("label"))
            if node_id in pos:
                node_x.append(pos[node_id][0])
                node_y.append(pos[node_id][1])
                node_text.append(node.get("label", node_id))
                # Node size based on degree or provided size
                size = node.get("size", G.degree(node_id) * 10 + 20)
                node_sizes.append(size)
                node_colors.append(node.get("color", "lightblue"))
        
        # Create edge traces
        edge_x = []
        edge_y = []
        edge_info = []
        
        for edge in spec.edges:
            source = edge["source"]
            target = edge["target"]
            if source in pos and target in pos:
                x0, y0 = pos[source]
                x1, y1 = pos[target]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])
                weight = edge.get("weight", 1)
                label = edge.get("label", f"res:{int(weight)}" if isinstance(weight, (int, float)) else "")
                edge_info.append({
                    "source": source,
                    "target": target,
                    "weight": weight,
                    "label": label,
                    "mid_x": (x0 + x1) / 2,
                    "mid_y": (y0 + y1) / 2,
                })
        
        fig = go.Figure()
        
        # Add edges
        if edge_x:
            fig.add_trace(go.Scatter(
                x=edge_x,
                y=edge_y,
                mode='lines',
                line=dict(width=1, color='#888'),
                hoverinfo='none',
                showlegend=False,
            ))
        
        # Add edge labels
        for info in edge_info:
            if info["label"]:
                fig.add_trace(go.Scatter(
                    x=[info["mid_x"]],
                    y=[info["mid_y"]],
                    mode='text',
                    text=[info["label"]],
                    textfont=dict(size=10),
                    showlegend=False,
                    hoverinfo='skip',
                ))
        
        # Add nodes
        fig.add_trace(go.Scatter(
            x=node_x,
            y=node_y,
            mode='markers+text',
            marker=dict(
                size=node_sizes,
                color=node_colors,
                line=dict(width=2, color='darkblue'),
            ),
            text=node_text,
            textposition="middle center",
            textfont=dict(size=12, color='black'),
            hoverinfo='text',
            hovertext=[f"Speaker: {text}" for text in node_text],
            showlegend=False,
        ))
        
        fig.update_layout(
            title=spec.title,
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20, l=5, r=5, t=40),
            annotations=[
                dict(
                    text="",
                    showarrow=False,
                    xref="paper", yref="paper",
                    x=0.005, y=-0.002,
                    xanchor="left", yanchor="bottom",
                    font=dict(color="#888", size=12)
                )
            ],
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        )
        return fig

    return None
