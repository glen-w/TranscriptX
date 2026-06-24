"""Highlights and Summary insights viewer — composed from layout profiles."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.layout_picker import render_layout_profile_picker
from transcriptx.web.blocks.rendering import render_block
from transcriptx.web.blocks.session_context import (
    build_context_from_session,
    load_active_layout,
)
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.services import RunIndex, SubjectService

_INSIGHTS_HELP = (
    "**Insights** shows curated narrative views from analysis modules "
    "(highlights, summary, LLM outputs)."
)


def render_insights() -> None:
    register_builtin_blocks()
    subject = SubjectService.resolve_current_subject(st.session_state)
    run_id = st.session_state.get("run_id")
    if not subject or not run_id:
        render_page_shell(
            "Insights",
            "Curated narrative views for the selected run.",
            badges=None,
            actions=None,
        )
        st.info("Select a subject and run to view insights.")
        render_page_help(_INSIGHTS_HELP)
        return

    run_root = RunIndex.get_run_root(
        subject.scope,
        run_id,
        subject_id=subject.subject_id,
    )
    if not run_root.exists():
        st.info("Run folder not found.")
        return

    render_page_shell(
        "Insights",
        "Themes, highlights, summaries, and LLM narrative outputs.",
        badges=None,
        actions=None,
        extra=lambda: render_layout_profile_picker(key_prefix="insights"),
    )

    ctx = build_context_from_session(st.session_state)
    if ctx is None:
        return

    layout = load_active_layout(st.session_state)
    page = layout.pages.get("insights")
    if page is None:
        st.warning("Active layout has no insights page.")
        return

    for index, block in enumerate(page.blocks):
        placement = block.to_placement()
        if index > 0:
            st.divider()
        render_block(placement.block_id, ctx, placement)

    render_page_help(_INSIGHTS_HELP)
