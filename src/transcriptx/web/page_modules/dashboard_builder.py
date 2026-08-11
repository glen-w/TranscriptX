"""Dashboard Builder — schema inspection, preview, and Save as custom layout."""

from __future__ import annotations

import re

import streamlit as st
import yaml

from transcriptx.web.blocks import register_builtin_blocks
from transcriptx.web.blocks.availability import check_block_availability
from transcriptx.web.blocks.composer import render_layout_page
from transcriptx.web.blocks.layout_picker import render_layout_profile_picker
from transcriptx.web.blocks.registry import list_blocks_by_group
from transcriptx.web.blocks.session_context import (
    active_layout_id,
    build_context_from_session,
    empty_context,
    load_active_layout,
    set_active_layout_id,
)
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.layouts.store import LayoutProfileStore, LayoutValidationError

_BUILDER_HELP_PREREQ = (
    "**Dashboard Builder** inspects registered view blocks and layout profiles. "
    "Built-in presets are previewable but immutable — use **Save as custom layout**."
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
        builtin = LayoutProfileStore.is_builtin(layout_id)
        title_note = " (built-in, read-only)" if builtin else ""
        st.write(f"**{layout.title}**{title_note} — {layout.description}")
        if builtin:
            st.info(
                "Built-in layouts cannot be edited in place. "
                "Use **Save as custom layout** below to clone."
            )
        st.code(
            yaml.safe_dump(layout.model_dump(mode="json"), sort_keys=False),
            language="yaml",
        )
        LayoutProfileStore.validate_layout(layout)
        st.success("Layout validation passed.")

        st.subheader("Save as custom layout")
        new_id = st.text_input(
            "New layout id",
            value=f"{layout_id}_custom" if builtin else f"{layout_id}_copy",
            key="dashboard_builder_save_as_id",
        )
        new_title = st.text_input(
            "Title",
            value=f"{layout.title} (custom)",
            key="dashboard_builder_save_as_title",
        )
        if st.button("Save as custom layout", key="dashboard_builder_save_as_btn"):
            slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", (new_id or "").strip())
            if not slug:
                st.error("Enter a valid layout id.")
            else:
                try:
                    path = LayoutProfileStore.save_as_custom(
                        layout, slug, title=new_title or slug
                    )
                    set_active_layout_id(slug)
                    st.success(f"Saved custom layout to {path}")
                    st.rerun()
                except LayoutValidationError as exc:
                    st.error(str(exc))
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
    # Dashboard Builder is the supported place to switch layouts (including built-in `all`).
    st.session_state["show_debug_layouts"] = True
    render_page_shell(
        "Dashboard Builder",
        "Inspect blocks, validate layouts, preview pages, and clone built-ins.",
        badges=None,
        actions=None,
    )

    layouts = LayoutProfileStore.list_layouts()
    if not layouts:
        st.error("No layout profiles found.")
        st.info(_BUILDER_HELP_PREREQ)
        return

    render_layout_profile_picker(key_prefix="dashboard_builder")
    chosen = active_layout_id()
    if chosen not in layouts:
        chosen = layouts[0]
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
