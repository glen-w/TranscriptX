"""Overview page blocks — adapted from page_modules/overview.py."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from transcriptx.core.pipeline.run_outcome_truth import (
    project_canonical_outcomes,
    project_group_outcomes,
)
from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.components.export_panel import render_export_panel_ui
from transcriptx.web.module_ui_groups import module_sort_key
from transcriptx.web.services.summary_service import SummaryService
from transcriptx.web.transcript_viewer.modules_panel import render_modules_panel


def render_run_health(ctx: BlockContext, _placement: BlockPlacement) -> None:
    health = ctx.health or {}
    status = health.get("status")
    has_errors = bool(health.get("errors"))
    has_warnings = bool(health.get("warnings"))
    has_issues = status in ("error", "warning") or has_errors or has_warnings

    if status == "error":
        st.error("🔴 Errors detected in this run.")
    elif status == "warning":
        st.warning("🟠 Warnings detected in this run.")

    if has_issues:
        if st.button("Re-scan health checks", key="block_run_health_rescan"):
            st.cache_data.clear()
            st.rerun()

    if health.get("errors"):
        with st.expander("Errors"):
            for item in health["errors"]:
                st.write(f"- {item}")
    if health.get("warnings"):
        with st.expander("Warnings"):
            for item in health["warnings"]:
                st.write(f"- {item}")


def render_run_outcomes(ctx: BlockContext, _placement: BlockPlacement) -> None:
    run_results = ctx.run_results
    run_root = ctx.run_root
    if not run_results or run_root is None:
        return
    if (Path(run_root) / "group_member_runs.json").exists():
        try:
            group_truth = project_group_outcomes(run_root)
            outcomes = group_truth.group_outcomes
        except Exception:
            outcomes = project_canonical_outcomes(run_results)
    else:
        outcomes = project_canonical_outcomes(run_results)
    skipped = [o for o in outcomes if o.status in {"skipped", "blocked"}]
    failed = [o for o in outcomes if o.status == "failed"]
    preset_explanation = run_results.get("preset_explanation")
    if not (skipped or failed or preset_explanation):
        return
    with st.expander(
        "Run summary (included / excluded)",
        expanded=bool(skipped or failed),
    ):
        if preset_explanation:
            st.caption("Preset explanation")
            st.text(preset_explanation)
        if failed:
            st.caption("Failed modules")
            for row in failed:
                detail = row.reason or ""
                if row.error_code:
                    prefix = f"[{row.error_code}]"
                    detail = f"{prefix} {detail}".strip()
                st.write(
                    f"- **{row.module_id}**: {detail or row.error_code or 'failed'}"
                )
        if skipped:
            st.caption("Skipped modules (reason)")
            for row in skipped:
                st.write(f"- **{row.module_id}** ({row.status}): {row.reason or ''}")


def render_artifact_metrics(ctx: BlockContext, _placement: BlockPlacement) -> None:
    artifacts = ctx.artifacts
    total_files = len(artifacts)
    chart_count = len([a for a in artifacts if a.kind.startswith("chart")])
    data_count = len([a for a in artifacts if a.kind.startswith("data")])
    total_size = sum(a.bytes for a in artifacts)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Artifacts", total_files)
    with col2:
        st.metric("Charts", chart_count)
    with col3:
        st.metric("Data Files", data_count)
    with col4:
        st.metric("Disk Size", f"{total_size / (1024 * 1024):.1f} MB")


def render_module_navigator(ctx: BlockContext, _placement: BlockPlacement) -> None:
    if ctx.subject_type != "transcript" or not ctx.session_name:
        st.caption("Module navigator is available for transcript runs.")
        return
    render_modules_panel(ctx.session_name)
    module = st.session_state.get("analysis_module")
    if module:
        from transcriptx.web.navigation import navigate_to_charts

        if st.button(
            "View charts for selected module",
            key="overview_nav_charts_module",
        ):
            navigate_to_charts(module=module)


def render_module_metrics(ctx: BlockContext, _placement: BlockPlacement) -> None:
    module = st.session_state.get("analysis_module")
    if not module:
        st.caption("Select an analysis module above to see extracted metrics.")
        return
    loader = ctx.services.content_loader
    if loader is None or ctx.run_root is None:
        st.caption("No module data available for this run.")
        return
    data = loader.load_first_module_json(str(module))
    summary = SummaryService.extract_analysis_summary(str(module), data)
    if not summary.get("has_data"):
        st.caption(f"No summary metrics available for **{module}**.")
        return
    st.subheader(f"Module metrics: {module}")
    metrics = summary.get("key_metrics") or {}
    if metrics:
        cols = st.columns(min(len(metrics), 4))
        for col, (key, value) in zip(cols, metrics.items()):
            col.metric(str(key).replace("_", " ").title(), str(value))
    highlights = summary.get("highlights") or []
    if highlights:
        st.caption("Highlights")
        for line in highlights[:8]:
            st.write(f"- {line}")


def render_module_summary_table(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Per-Module Summary")
    module_map: dict[str, dict[str, object]] = {}
    for artifact in ctx.artifacts:
        module = artifact.module or "other"
        module_map.setdefault(module, {"charts": 0, "data": 0, "last": None})
        if artifact.kind.startswith("chart"):
            module_map[module]["charts"] += 1
        if artifact.kind.startswith("data"):
            module_map[module]["data"] += 1
        module_map[module]["last"] = max(
            module_map[module]["last"] or artifact.mtime, artifact.mtime
        )
    table_data = []
    for module, stats in sorted(
        module_map.items(), key=lambda item: module_sort_key(item[0])
    ):
        table_data.append(
            {
                "Module": module,
                "Charts": stats["charts"],
                "Data Files": stats["data"],
                "Last Updated": stats["last"] if stats["last"] else "N/A",
            }
        )
    df = pd.DataFrame(table_data)
    st.dataframe(
        df,
        width="stretch",
        hide_index=True,
        height=min(400, 50 + len(df) * 35),
    )


def render_export_panel(ctx: BlockContext, _placement: BlockPlacement) -> None:
    if ctx.run_root is None:
        st.info("Select a run to export artifacts.")
        return
    render_export_panel_ui(ctx.run_root, ctx.artifacts, key_prefix="overview_export")
