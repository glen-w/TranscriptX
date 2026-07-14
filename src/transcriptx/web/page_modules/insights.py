"""Insights viewer — sectioned composition from layout profiles."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.blocks.builtin import register_builtin_blocks
from transcriptx.web.blocks.rendering import render_block
from transcriptx.web.blocks.session_context import (
    build_context_from_session,
    load_active_layout,
)
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.run_scoped_page import (
    RunScopedPageConfig,
    RunScopedPageContext,
    render_run_scoped_page,
)

INSIGHTS_SECTION_KEY = "insights_section"
INSIGHTS_SECTIONS = (
    ("summary", "Summary"),
    ("speakers", "Speakers"),
    ("actions", "Actions"),
    ("highlights", "Highlights"),
    ("analysis", "Analysis"),
)

_INSIGHTS_HELP_PREREQ = (
    "**Insights** is a structured analysis workspace for summaries, speakers, "
    "actions, highlights, and deeper analysis."
)

_INSIGHTS_CONFIG = RunScopedPageConfig(
    title="Insights",
    description="Structured analysis for the selected run.",
    prereq_help_md=_INSIGHTS_HELP_PREREQ,
    empty_headline="Select a subject and run",
    empty_detail="Use the sidebar to choose a transcript or group, then pick a run.",
    primary_action=("Open Library", "Library"),
    secondary_action=("Run Analysis", "Run Analysis"),
    loaded_help_md=None,
)


def _render_section_nav() -> str:
    labels = [label for _, label in INSIGHTS_SECTIONS]
    keys = [key for key, _ in INSIGHTS_SECTIONS]
    current = st.session_state.get(INSIGHTS_SECTION_KEY, "summary")
    if current not in keys:
        current = "summary"
        st.session_state[INSIGHTS_SECTION_KEY] = current
    try:
        choice = st.segmented_control(
            "Insights section",
            options=labels,
            default=dict(INSIGHTS_SECTIONS)[current],
            key="insights_section_control",
            label_visibility="collapsed",
        )
    except Exception:
        choice = st.radio(
            "Insights section",
            labels,
            index=keys.index(current),
            horizontal=True,
            key="insights_section_radio",
            label_visibility="collapsed",
        )
    selected_key = next(k for k, lab in INSIGHTS_SECTIONS if lab == choice)
    st.session_state[INSIGHTS_SECTION_KEY] = selected_key
    return selected_key


@st.fragment
def _insights_sections_fragment(block_ctx, layout) -> None:
    """Section nav + block rendering; switching sections reruns only this fragment."""
    section = _render_section_nav()

    if block_ctx is None:
        return

    page = layout.pages.get("insights") if layout is not None else None
    if page is None:
        st.warning("Active layout has no insights page.")
        return

    placements = [b.to_placement() for b in page.blocks]
    section_blocks = [
        p for p in placements if (p.section or "analysis") == section and p.visible
    ]
    # Layouts without section tags (v1 executive): show all on Summary only.
    if not any(p.section for p in placements):
        if section != "summary":
            st.info(
                "This layout does not define sections. Switch to Summary, or open Dashboard Builder."
            )
            return
        section_blocks = [p for p in placements if p.visible]

    if not section_blocks:
        st.info("No blocks for this section in the active layout.")
        return

    for index, placement in enumerate(section_blocks):
        if index > 0:
            st.divider()
        render_block(placement.block_id, block_ctx, placement)


def _render_insights_body(ctx: RunScopedPageContext) -> None:
    render_page_shell(
        "Insights",
        "Themes, summaries, speakers, actions, and deeper analysis.",
        badges=None,
        actions=None,
    )
    block_ctx = build_context_from_session(st.session_state)
    layout = load_active_layout(st.session_state) if block_ctx is not None else None
    _insights_sections_fragment(block_ctx, layout)


def render_insights() -> None:
    register_builtin_blocks()
    render_run_scoped_page(_INSIGHTS_CONFIG, render_body=_render_insights_body)
