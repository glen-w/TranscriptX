"""Streamlit configuration page."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
import copy
import streamlit as st

from transcriptx.core.config import (
    build_registry,
    flatten,
    unflatten,
    get_default_config_dict,
    load_project_config,
    save_project_config,
    load_draft_override,
    save_draft_override,
    load_run_effective,
    resolve_effective_config,
    validate_config,
)
from transcriptx.web.services import FileService
from transcriptx.web.ui.settings import render_config_form, render_config_diff


def _get_run_dir() -> Optional[Path]:
    session = st.session_state.get("selected_session")
    run_id = st.session_state.get("selected_run_id")
    if not session or not run_id:
        return None
    return FileService._resolve_session_dir(f"{session}/{run_id}")


def _load_effective_config(run_dir: Optional[Path]) -> Dict[str, Any]:
    if run_dir is None:
        return get_default_config_dict()
    effective = load_run_effective(run_dir)
    if effective:
        return effective
    resolved = resolve_effective_config(run_dir=run_dir)
    return resolved.effective_dict_nested


def render_configuration_page() -> None:
    st.header("Configuration")
    run_dir = _get_run_dir()
    effective_config = _load_effective_config(run_dir)
    resolved = resolve_effective_config(run_dir=run_dir) if run_dir else None
    sources = resolved.sources_by_key if resolved else {}

    st.subheader("Effective Config (Selected Run)")
    col_left, col_right = st.columns([3, 1])
    with col_right:
        st.download_button(
            "Download JSON",
            data=json.dumps(effective_config, indent=2),
            file_name="run_config_effective.json",
            mime="application/json",
        )
        st.code(json.dumps(effective_config, indent=2), language="json")

    registry = build_registry()
    effective_dot = flatten(effective_config)
    categories = sorted({meta.category for meta in registry.values()})

    with col_left:
        for category in categories:
            keys = [k for k in effective_dot.keys() if k.startswith(f"{category}.")]
            if not keys:
                continue
            with st.expander(category.title(), expanded=False):
                for key in sorted(keys):
                    value = effective_dot.get(key)
                    source = sources.get(key, "default")
                    st.write(f"`{key}`")
                    st.caption(f"source: {source}")
                    st.json(value)

    st.divider()
    st.subheader("Edit Configuration")

    scope = st.selectbox(
        "Scope",
        options=["Default", "Project", "Draft Override"],
        index=1,
        key="config_scope",
    )
    st.caption(f"Editing scope: {scope}")
    edit_mode = st.toggle("Edit Mode", value=False, key="config_edit_mode")
    show_only_changed = st.toggle(
        "Show only changed settings", value=False, key="config_changed_only"
    )

    defaults = get_default_config_dict()
    project = load_project_config() or {}
    draft = load_draft_override() or {}

    if scope == "Default":
        base_config = defaults
    elif scope == "Project":
        base_config = project or defaults
    else:
        base_config = draft or {}

    if "config_draft" not in st.session_state or st.session_state.get(
        "config_scope_cache"
    ) != scope:
        st.session_state["config_draft"] = copy.deepcopy(base_config)
        st.session_state["config_scope_cache"] = scope

    draft_config = st.session_state.get("config_draft") or {}
    draft_dot = flatten(draft_config)
    base_dot = flatten(base_config)

    if not edit_mode and scope != "Default":
        st.info("Enable edit mode to modify settings.")

    if edit_mode:
        for category in categories:
            fields = [meta for meta in registry.values() if meta.category == category]
            if not fields:
                continue
            with st.expander(category.title(), expanded=False):
                updated = render_config_form(
                    category=category,
                    fields=fields,
                    values=draft_dot,
                    show_only_changed=show_only_changed,
                    base_values=base_dot,
                    scope=scope.lower().replace(" ", "_"),
                )
                draft_dot.update(updated)

        draft_config = unflatten(draft_dot)
        st.session_state["config_draft"] = draft_config

        errors = validate_config(draft_config)
        if errors:
            st.error("Validation errors detected. Fix before saving.")
            for key, items in errors.items():
                for err in items:
                    st.caption(f"{key}: {err.message}")

        render_config_diff(base_config, draft_config)

        col_save, col_reset, col_revert = st.columns(3)
        with col_save:
            if st.button("Save", disabled=bool(errors) or scope == "Default"):
                if scope == "Project":
                    save_project_config(draft_config)
                elif scope == "Draft Override":
                    save_draft_override(draft_config)
                st.success("Configuration saved.")
                st.rerun()
        with col_reset:
            if st.button("Reset"):
                st.session_state["config_draft"] = copy.deepcopy(base_config)
                st.rerun()
        with col_revert:
            if st.button("Revert to Defaults"):
                st.session_state["config_draft"] = copy.deepcopy(defaults)
                st.rerun()
