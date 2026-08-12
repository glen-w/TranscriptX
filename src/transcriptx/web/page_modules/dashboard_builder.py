"""Dashboard Builder — layout edit, schema inspection, preview, and custom clones."""

from __future__ import annotations

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
    set_active_layout_id,
)
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.layouts.store import (
    LayoutProfileStore,
    LayoutValidationError,
    slugify_layout_id,
)
from transcriptx.web.ui.dashboard_builder.layout_editor import render_layout_editor

_BUILDER_HELP_PREREQ = (
    "**Dashboard Builder** chooses which panels appear on **Overview** and **Insights** "
    "(layout profiles). It does **not** pick Charts overview charts — use "
    "**Settings → Configuration → Charts overview**. "
    "Built-in presets are immutable; clone with **Save as custom layout**. "
    "Visiting this page enables the **Developer debug** layout in the picker for the session."
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
    except LayoutValidationError as exc:
        st.error(f"Layout validation failed: {exc}")
        return
    except FileNotFoundError as exc:
        st.error(str(exc))
        return

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
    try:
        LayoutProfileStore.validate_layout(layout)
        st.success("Layout validation passed.")
    except LayoutValidationError as exc:
        st.error(f"Layout validation failed: {exc}")
        return

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
    exists = False
    try:
        preview_slug = slugify_layout_id(new_id) if (new_id or "").strip() else ""
        exists = bool(
            preview_slug
            and not LayoutProfileStore.is_builtin(preview_slug)
            and LayoutProfileStore.custom_layout_exists(preview_slug)
        )
    except LayoutValidationError:
        preview_slug = ""
    overwrite_ok = True
    if exists:
        overwrite_ok = st.checkbox(
            f"Overwrite existing custom layout `{preview_slug}`",
            value=False,
            key="dashboard_builder_overwrite_confirm",
        )
        if not overwrite_ok:
            st.caption("A custom layout with this id already exists.")
    if st.button("Save as custom layout", key="dashboard_builder_save_as_btn"):
        try:
            slug = slugify_layout_id(new_id or "")
            if LayoutProfileStore.custom_layout_exists(slug) and not overwrite_ok:
                st.error(
                    f"Custom layout '{slug}' already exists. "
                    "Confirm overwrite to replace it."
                )
            else:
                path = LayoutProfileStore.save_as_custom(
                    layout,
                    slug,
                    title=new_title or slug,
                    overwrite=True,
                )
                set_active_layout_id(slug)
                st.success(f"Saved custom layout to {path}")
                st.rerun()
        except LayoutValidationError as exc:
            st.error(str(exc))

    if not builtin:
        st.subheader("Delete custom layout")
        st.caption("Built-in presets cannot be deleted.")
        confirm_delete = st.checkbox(
            f"Confirm delete `{layout_id}`",
            value=False,
            key="dashboard_builder_delete_confirm",
        )
        if st.button(
            "Delete custom layout",
            key="dashboard_builder_delete_btn",
            disabled=not confirm_delete,
        ):
            try:
                path = LayoutProfileStore.delete_custom(layout_id)
                if active_layout_id() == layout_id:
                    set_active_layout_id("default")
                st.success(f"Deleted custom layout {path}")
                st.rerun()
            except (LayoutValidationError, FileNotFoundError) as exc:
                st.error(str(exc))


def _render_preview_mode(layout_id: str) -> None:
    ctx = build_context_from_session(st.session_state, layout_profile_id=layout_id)
    if ctx is None:
        st.info("Select a subject and run in the sidebar to preview blocks.")
        return
    try:
        layout = LayoutProfileStore.load_layout(layout_id)
    except (LayoutValidationError, FileNotFoundError) as exc:
        st.error(str(exc))
        return
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
        "Edit Overview/Insights layouts, validate YAML, preview pages, and clone built-ins.",
        badges=None,
        actions=None,
    )

    layouts = LayoutProfileStore.list_layouts()
    if not layouts:
        st.error("No layout profiles found.")
        st.info(_BUILDER_HELP_PREREQ)
        return

    st.info(_BUILDER_HELP_PREREQ)
    render_layout_profile_picker(key_prefix="dashboard_builder")
    chosen = active_layout_id()
    if chosen not in layouts:
        chosen = layouts[0]
        set_active_layout_id(chosen)

    mode = st.radio(
        "Mode",
        ["Edit", "Schema", "Preview"],
        horizontal=True,
        key="dashboard_builder_mode",
    )

    if mode == "Edit":
        render_layout_editor(chosen)
    elif mode == "Schema":
        _render_schema_mode(chosen)
    else:
        _render_preview_mode(chosen)
