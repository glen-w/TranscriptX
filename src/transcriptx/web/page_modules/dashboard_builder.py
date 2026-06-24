"""Dashboard Builder — schema inspection and layout preview (Phase 1)."""

from __future__ import annotations

import streamlit as st
import yaml

from transcriptx.web.blocks import register_builtin_blocks  # noqa: F401 — side effect
from transcriptx.web.blocks.availability import check_block_availability
from transcriptx.web.blocks.composer import render_layout_page
from transcriptx.web.blocks.registry import list_blocks_by_group
from transcriptx.web.blocks.session_context import (
    active_layout_id,
    build_context_from_session,
    empty_context,
    load_active_layout,
    set_active_layout_id,
)
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.layouts.store import LayoutProfileStore, LayoutValidationError

_BUILDER_HELP = (
    "**Dashboard Builder** inspects registered view blocks and layout profiles. "
    "**Schema** mode works without a run; **Preview** renders blocks for the selected run."
)


def _render_schema_mode(layout_id: str) -> None:
    st.subheader("Registered blocks")
    grouped = list_blocks_by_group()
    ctx = empty_context(layout_id)
    for group, specs in grouped.items():
        with st.expander(group, expanded=False):
            for spec in specs:
                availability = check_block_availability(spec, ctx)
                status = "available" if availability.available else "unavailable"
                st.markdown(f"**`{spec.id}`** — {spec.description}")
                st.caption(f"Status (no run): {status}")
                if availability.reason:
                    st.caption(availability.reason)

    st.subheader("Active layout profile")
    try:
        layout = LayoutProfileStore.load_layout(layout_id)
        st.write(f"**{layout.title}** — {layout.description}")
        st.code(
            yaml.safe_dump(layout.model_dump(mode="json"), sort_keys=False),
            language="yaml",
        )
        LayoutProfileStore.validate_layout(layout)
        st.success("Layout validation passed.")
    except LayoutValidationError as exc:
        st.error(f"Layout validation failed: {exc}")
    except FileNotFoundError as exc:
        st.error(str(exc))


def _render_preview_mode(layout_id: str) -> None:
    ctx = build_context_from_session(st.session_state, layout_profile_id=layout_id)
    if ctx is None:
        st.info("Select a subject and run in the sidebar to preview blocks.")
        return
    layout = load_active_layout(st.session_state)
    preview_page = st.selectbox(
        "Preview page",
        options=sorted(layout.pages.keys()),
        key="dashboard_builder_preview_page",
    )
    st.subheader(f"Preview: {preview_page}")
    grouped = list_blocks_by_group()
    with st.expander("Block availability for current run", expanded=False):
        for group, specs in grouped.items():
            for spec in specs:
                availability = check_block_availability(spec, ctx)
                label = "ok" if availability.available else "missing"
                matched = ", ".join(availability.matched_artifacts) or "—"
                st.caption(f"`{spec.id}` ({group}): {label} · artifacts: {matched}")
                if availability.reason:
                    st.caption(availability.reason)
    render_layout_page(preview_page, ctx, layout)


def render_dashboard_builder() -> None:
    register_builtin_blocks()
    render_page_shell(
        "Dashboard Builder",
        "Inspect blocks, validate layouts, and preview composed pages.",
        badges=None,
        actions=None,
    )

    layouts = LayoutProfileStore.list_layouts()
    if not layouts:
        st.error("No layout profiles found.")
        render_page_help(_BUILDER_HELP)
        return

    current = active_layout_id()
    if current not in layouts:
        current = layouts[0]
    layout_index = layouts.index(current)
    chosen = st.selectbox(
        "Layout profile",
        layouts,
        index=layout_index,
        key="dashboard_builder_layout_select",
    )
    if chosen != active_layout_id():
        set_active_layout_id(chosen)

    mode = st.radio(
        "Mode",
        ["Schema", "Preview"],
        horizontal=True,
        key="dashboard_builder_mode",
    )

    if mode == "Schema":
        _render_schema_mode(chosen)
    else:
        _render_preview_mode(chosen)

    render_page_help(_BUILDER_HELP)
