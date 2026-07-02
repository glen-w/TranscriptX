"""
Overview dashboard page for TranscriptX Studio.

Body content is composed from layout profiles via the block registry.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.layout_picker import render_layout_profile_picker
from transcriptx.web.blocks.rendering import render_block
from transcriptx.web.blocks.session_context import (
    build_context_from_session,
    load_active_layout,
)
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.components.run_scoped_page import (
    RunScopedPageConfig,
    RunScopedPageContext,
    render_run_scoped_page,
)
from transcriptx.web.services import ArtifactService

_OVERVIEW_HELP_PREREQ = "**Overview** shows artifact counts, module summaries, and export options for one run."
_OVERVIEW_HELP_LOADED = (
    "**Overview** aggregates artifacts for the current run. Warnings here reflect "
    "manifest checks, not full pipeline logs."
)

_OVERVIEW_CONFIG = RunScopedPageConfig(
    title="Overview",
    description="Summary of artifacts and health for the selected run.",
    prereq_help_md=_OVERVIEW_HELP_PREREQ,
    empty_headline="Select a subject and run",
    empty_detail="Use the sidebar to choose a transcript or group, then pick a run.",
    primary_action=("Open Library", "Library"),
    secondary_action=("Run Analysis", "Run Analysis"),
    loaded_help_md=_OVERVIEW_HELP_LOADED,
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
    artifacts = ArtifactService.list_artifacts(ctx.run_root)
    health = ArtifactService.check_run_health(ctx.run_root)
    status = health.get("status")
    badge_health = "Artifact Health: Healthy"
    if status == "error":
        badge_health = "Artifact Health: Missing"
    elif status == "warning" or health.get("warnings"):
        badge_health = "Artifact Health: Partial"

    render_page_shell(
        "Overview",
        f"Run started: {run_datetime}. Browse artifacts and export selections.",
        badges=[badge_health],
        actions=None,
        extra=lambda: render_layout_profile_picker(key_prefix="overview"),
    )

    if not artifacts:
        render_empty_state(
            "no_results_yet",
            "No artifacts for this run",
            "This run folder exists but lists no artifacts yet, or analysis did not write outputs.",
            primary_action=("Run Analysis", "Run Analysis"),
            secondary_action=("Diagnostics", "Diagnostics"),
        )
        render_page_help(_OVERVIEW_HELP_LOADED)
        return

    session_ctx = build_context_from_session(st.session_state)
    if session_ctx is None:
        render_page_help(_OVERVIEW_HELP_LOADED)
        return

    layout = load_active_layout(st.session_state)
    page = layout.pages.get("overview")
    if page is None:
        st.warning("Active layout has no overview page.")
        return

    placements = [b.to_placement() for b in page.blocks]
    for index, placement in enumerate(placements):
        if placement.block_id == "module_summary_table" and index > 0:
            st.divider()
        render_block(placement.block_id, session_ctx, placement)
        if placement.block_id == "module_navigator":
            st.divider()
        if placement.block_id == "module_metrics":
            st.divider()

    render_page_help(_OVERVIEW_HELP_LOADED)


def render_overview() -> None:
    register_builtin_blocks()
    render_run_scoped_page(_OVERVIEW_CONFIG, render_body=_render_overview_body)
