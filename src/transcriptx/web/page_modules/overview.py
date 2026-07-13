"""
Overview dashboard page for TranscriptX Studio.

Body content is composed from layout profiles via the block registry.
Standard (default) layout is curated; layout picker is not shown here.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.rendering import render_block
from transcriptx.web.blocks.session_context import (
    build_context_from_session,
    load_active_layout,
)
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.run_scoped_page import (
    RunScopedPageConfig,
    RunScopedPageContext,
    render_run_scoped_page,
)
from transcriptx.web.services.artifact_index import build_artifact_index

_OVERVIEW_HELP_PREREQ = (
    "**Overview** is a curated landing page for one run: summary, speakers, "
    "actions, highlights, and quiet run status."
)

_OVERVIEW_CONFIG = RunScopedPageConfig(
    title="Overview",
    description="What this recording is and what to know first.",
    prereq_help_md=_OVERVIEW_HELP_PREREQ,
    empty_headline="Select a subject and run",
    empty_detail="Use the sidebar to choose a transcript or group, then pick a run.",
    primary_action=("Open Library", "Library"),
    secondary_action=("Run Analysis", "Run Analysis"),
    loaded_help_md=None,
)


def _parse_run_datetime(run_id: str) -> str:
    try:
        if "_" in run_id:
            date_time_str = run_id.split("_")[0] + "_" + run_id.split("_")[1]
            dt = datetime.strptime(date_time_str, "%Y%m%d_%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        pass
    return run_id


def _render_overview_body(ctx: RunScopedPageContext) -> None:
    run_datetime = _parse_run_datetime(ctx.run_id)
    index = build_artifact_index(
        ctx.run_root,
        subject_scope=str(ctx.subject.subject_type),
        subject_id=ctx.subject.subject_id,
        run_id=ctx.run_id,
    )
    render_page_shell(
        "Overview",
        f"Run started: {run_datetime}.",
        badges=None,
        actions=None,
    )

    if not index.entries:
        render_empty_state(
            "no_results_yet",
            "No artifacts for this run",
            "This run folder exists but lists no artifacts yet, or analysis did not write outputs.",
            primary_action=("Run Analysis", "Run Analysis"),
            secondary_action=("Diagnostics", "Diagnostics"),
        )
        return

    session_ctx = build_context_from_session(st.session_state)
    if session_ctx is None:
        return

    layout = load_active_layout(st.session_state)
    page = layout.pages.get("overview")
    if page is None:
        st.warning("Active layout has no overview page.")
        return

    placements = [b.to_placement() for b in page.blocks]
    for index_i, placement in enumerate(placements):
        if index_i > 0:
            st.divider()
        render_block(placement.block_id, session_ctx, placement)


def render_overview() -> None:
    register_builtin_blocks()
    render_run_scoped_page(_OVERVIEW_CONFIG, render_body=_render_overview_body)
