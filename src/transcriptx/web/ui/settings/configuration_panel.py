"""Settings configuration subview — effective config readout and scoped editing."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

from transcriptx.core.config import (
    build_registry,
    flatten,
    get_default_config_dict,
    get_draft_override_path,
    get_project_config_path,
    get_run_override_path,
    load_draft_override,
    load_project_config,
    load_run_override,
    resolve_effective_config,
    save_draft_override,
    save_project_config,
    save_run_override,
    unflatten,
    validate_config,
)
from transcriptx.web.ui.settings.diff_view import render_config_diff
from transcriptx.web.ui.settings.forms import render_config_form

_SCOPE_KEYS = ("Default", "Project", "Draft override", "Run override")
_SCOPE_WIDGET_KEY = "settings_config_scope_ix"
_SCOPE_CACHE_KEY = "settings_config_scope_cache"
_DRAFT_STATE_KEY = "settings_config_draft"


def _scope_labels(run_dir: Optional[Path]) -> list[str]:
    labels = list(_SCOPE_KEYS)
    if run_dir is None:
        labels[3] = "Run override — select a run in the sidebar"
    return labels


def _coerce_scope_index_if_needed(run_dir: Optional[Path]) -> None:
    if _SCOPE_WIDGET_KEY not in st.session_state:
        st.session_state[_SCOPE_WIDGET_KEY] = 1
    if run_dir is None and st.session_state.get(_SCOPE_WIDGET_KEY) == 3:
        st.session_state[_SCOPE_WIDGET_KEY] = 1


def _scope_name_from_index(ix: int) -> str:
    return _SCOPE_KEYS[ix]


def _save_target(scope: str, run_dir: Optional[Path]) -> tuple[str, str]:
    """Return (human scope label, filesystem path string)."""
    if scope == "Project":
        p = get_project_config_path()
        return "Project config", str(p.resolve())
    if scope == "Draft override":
        p = get_draft_override_path()
        return "Draft override", str(p.resolve())
    if scope == "Run override":
        assert run_dir is not None
        p = get_run_override_path(run_dir)
        return "Run override", str(p.resolve())
    return "Default", ""


def render_configuration_panel(
    *,
    run_dir: Optional[Path],
    subject_display: Optional[str],
    run_display: Optional[str],
    show_title: bool = False,
) -> None:
    """
    Configuration UI: effective readout (resolver-only) and scoped editing.

    Does not read st.session_state for run/subject resolution — caller passes
    run_dir and display strings explicitly.
    """
    if show_title:
        st.subheader("Configuration")

    resolved = resolve_effective_config(run_dir=run_dir)
    effective_config = resolved.effective_dict_nested
    sources = resolved.sources_by_key

    subj = subject_display or "—"
    run_l = run_display or "—"
    if run_dir is not None:
        eff_title = "Effective configuration (selected run)"
        eff_caption = f"Subject: {subj} · Run: {run_l}"
    else:
        eff_title = "Effective configuration (workspace)"
        eff_caption = (
            f"Subject: {subj} · Run: {run_l} · "
            "Select a subject and run in the sidebar to include run-level overrides in this readout."
        )

    st.subheader(eff_title)
    st.caption(eff_caption)

    st.caption(
        "Precedence (later wins per key): Environment → Run override (or draft when no run "
        "folder) → Project config → Defaults."
    )

    col_left, col_right = st.columns([3, 1])
    with col_right:
        dl_name = (
            "run_config_effective.json"
            if run_dir is not None
            else "workspace_config_effective.json"
        )
        st.download_button(
            "Download JSON",
            data=json.dumps(effective_config, indent=2),
            file_name=dl_name,
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
    st.subheader("Edit configuration")
    st.caption(
        "Effective configuration (above) is what the app uses. Below, choose which **layer** "
        "you are editing — not the same as effective unless that layer is last in precedence."
    )

    _coerce_scope_index_if_needed(run_dir)
    labels = _scope_labels(run_dir)
    scope_ix = st.selectbox(
        "Editing scope",
        options=list(range(4)),
        format_func=lambda i: labels[i],
        key=_SCOPE_WIDGET_KEY,
    )
    scope = _scope_name_from_index(int(scope_ix))

    if run_dir is None:
        st.caption(
            "**Run override** appears in the list above; choose it after selecting a subject and run "
            "in the sidebar. Until then, picking it snaps back to another scope."
        )

    defaults = get_default_config_dict()
    project = load_project_config() or {}
    draft = load_draft_override() or {}
    run_ov: Dict[str, Any] = {}
    if run_dir is not None:
        run_ov = load_run_override(run_dir) or {}

    if scope == "Default":
        base_config = defaults
    elif scope == "Project":
        base_config = project or defaults
    elif scope == "Draft override":
        base_config = draft or {}
    else:
        base_config = run_ov if run_dir is not None else {}

    scope_cache = st.session_state.get(_SCOPE_CACHE_KEY)
    if _DRAFT_STATE_KEY not in st.session_state or scope_cache != scope:
        st.session_state[_DRAFT_STATE_KEY] = copy.deepcopy(base_config)
        st.session_state[_SCOPE_CACHE_KEY] = scope

    draft_config = st.session_state.get(_DRAFT_STATE_KEY) or {}
    draft_dot = flatten(draft_config)
    base_dot = flatten(base_config)

    edit_mode = st.toggle("Edit mode", value=False, key="settings_config_edit_mode")
    show_only_changed = st.toggle(
        "Show only changed settings", value=False, key="settings_config_changed_only"
    )

    if scope == "Default":
        st.info(
            "**Default** is read-only built-in defaults — a baseline for inheritance. Enable **Edit mode** on **Project** or **Draft override** (or **Run override** when a run is selected) to save changes."
        )
    elif not edit_mode:
        st.info("Enable **edit mode** to modify settings for this scope.")

    form_scope_key = scope.lower().replace(" ", "_")

    if edit_mode and scope != "Default":
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
                    scope=form_scope_key,
                )
                draft_dot.update(updated)

        draft_config = unflatten(draft_dot)
        st.session_state[_DRAFT_STATE_KEY] = draft_config

        errors = validate_config(draft_config)
        if errors:
            st.error("Validation errors detected. Fix before saving.")
            for key, items in errors.items():
                for err in items:
                    st.caption(f"{key}: {err.message}")

        render_config_diff(base_config, draft_config)

        save_label_scope, save_path = _save_target(scope, run_dir)
        st.caption(f"**Save target:** {save_label_scope} → `{save_path}`")

        can_save = (
            not bool(errors)
            and scope != "Default"
            and not (scope == "Run override" and run_dir is None)
        )
        save_btn = (
            f"Save {save_label_scope}"
            if scope != "Default"
            else "Save (disabled for Default)"
        )

        col_save, col_reset, col_revert = st.columns(3)
        with col_save:
            if st.button(save_btn, disabled=not can_save, key="settings_config_save"):
                if scope == "Project":
                    save_project_config(draft_config)
                elif scope == "Draft override":
                    save_draft_override(draft_config)
                elif scope == "Run override" and run_dir is not None:
                    save_run_override(run_dir, draft_config)
                st.success(f"Saved **{save_label_scope}** to `{save_path}`.")
                st.rerun()
        with col_reset:
            if st.button("Reset", key="settings_config_reset"):
                st.session_state[_DRAFT_STATE_KEY] = copy.deepcopy(base_config)
                st.rerun()
        with col_revert:
            if st.button("Revert to defaults", key="settings_config_revert"):
                st.session_state[_DRAFT_STATE_KEY] = copy.deepcopy(defaults)
                st.rerun()
