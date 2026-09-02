"""View → Performance: analysis-run timing (not Streamlit UI load profiling)."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.components.run_scoped_page import (
    RunScopedPageConfig,
    RunScopedPageContext,
    render_run_scoped_page,
)
from transcriptx.web.services.run_performance_service import build_run_performance_view


def _format_metric_duration_ms(duration_ms: float | None) -> str:
    """Format metric durations: sub-minute as seconds, else mins/secs (hours if needed)."""
    if duration_ms is None:
        return "—"
    seconds = float(duration_ms) / 1000.0
    if seconds < 60:
        return f"{seconds:.2f}s"
    total = int(seconds)
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    return f"{minutes}m {secs}s"


def render_performance() -> None:
    render_run_scoped_page(
        RunScopedPageConfig(
            title="Performance",
            description=(
                "Observed analysis-run timing for the selected run. "
                "Comparisons are observational; settings are not claimed as causes."
            ),
            empty_headline="Select a run to view performance",
            empty_detail="Choose a transcript or group and a completed analysis run.",
            primary_action=("Run Analysis", "Run Analysis"),
            secondary_action=("Overview", "Overview"),
        ),
        render_body=_render_body,
    )


def _render_body(ctx: RunScopedPageContext) -> None:
    vm = build_run_performance_view(ctx.run_root)

    for note in vm.provenance_notes:
        st.caption(note)

    cols = st.columns(4)
    cols[0].metric("Wall clock", _format_metric_duration_ms(vm.wall_clock_duration_ms))
    cols[1].metric(
        "Cumulative modules",
        _format_metric_duration_ms(vm.derived.module_duration_sum_ms),
    )
    cols[2].metric(
        "Unattributed",
        _format_metric_duration_ms(vm.derived.unattributed_duration_ms),
    )
    cols[3].metric("Sidecar", vm.performance_status.value)

    st.caption(
        "Module % is of cumulative measured module time, not wall clock. "
        "Modules may not overlap today; cumulative and wall can still differ."
    )

    if not vm.derived.rows:
        st.info("No module duration rows available for this run.")
        return

    table = [
        {
            "module": r.module_id,
            "status": r.status,
            "duration_s": (
                None if r.duration_ms is None else round(r.duration_ms / 1000.0, 3)
            ),
            "pct_cumulative": (
                None if r.pct_of_cumulative is None else round(r.pct_of_cumulative, 1)
            ),
            "cached": r.used_cache,
            "used_llm": r.used_llm,
        }
        for r in vm.derived.rows
    ]
    st.dataframe(table, width="stretch", hide_index=True)

    if vm.llm:
        st.subheader("LLM (bounded aggregates)")
        st.json(
            {
                "call_count": vm.llm.get("call_count"),
                "success_count": vm.llm.get("success_count"),
                "failure_count": vm.llm.get("failure_count"),
                "retry_count": vm.llm.get("retry_count"),
                "logical_wall_ms": vm.llm.get("logical_wall_ms"),
                "tokens_per_second": vm.llm.get("tokens_per_second"),
                "models": vm.llm.get("models"),
                "efforts": vm.llm.get("efforts"),
            }
        )
