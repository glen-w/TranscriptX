"""Settings configuration subview — effective config readout and scoped editing."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

from transcriptx.core.config import (
    COMMON_SETTINGS_SCHEMA,
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
    iter_all_profile_target_adapters,
    strip_activation_keys_from_flat_map,
    strip_activation_keys_from_nested_map,
)
from transcriptx.web.ui.settings.diff_view import render_config_diff
from transcriptx.web.ui.settings.forms import render_config_form

_SCOPE_KEYS = ("Default", "Project", "Draft override", "Run override")
_SCOPE_WIDGET_KEY = "settings_config_scope_ix"
_SCOPE_CACHE_KEY = "settings_config_scope_cache"
_DRAFT_STATE_KEY = "settings_config_draft"
_RUN_CACHE_KEY = "settings_config_run_cache"


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


def _should_reset_draft_state(
    session_state: dict[str, Any], *, scope: str, current_run_cache: str
) -> bool:
    scope_cache = session_state.get(_SCOPE_CACHE_KEY)
    run_cache = session_state.get(_RUN_CACHE_KEY)
    return (
        _DRAFT_STATE_KEY not in session_state
        or scope_cache != scope
        or run_cache != current_run_cache
    )


def _strip_activation_keys(config_map: dict[str, Any]) -> dict[str, Any]:
    """Return config map without adapter-owned activation keys."""
    return strip_activation_keys_from_flat_map(config_map)


def _sanitize_scope_config(scope: str, config_map: dict[str, Any]) -> dict[str, Any]:
    """Return a scope-safe config payload for editor state/persistence."""
    if scope == "Draft override":
        return strip_activation_keys_from_nested_map(config_map)
    return config_map


def _render_effective_value(value: Any) -> None:
    """Render a resolved config value without Streamlit JSON-viewer pitfalls.

    ``st.json`` treats Python ``str`` as already-serialized JSON (so paths like
    ``/mnt/outputs`` fail to parse) and some Streamlit versions reject JSON
    primitives (bool/number/null) with "src property must be a valid json object".
    """
    if isinstance(value, (dict, list)):
        st.json(value)
    else:
        st.code(json.dumps(value), language="json")


def _render_active_profile_selectors(
    *,
    draft_dot: dict[str, Any],
    scope: str,
    form_scope_key: str,
) -> None:
    from transcriptx.app.controllers.profile_controller import ProfileController

    if scope not in ("Project", "Run override"):
        st.caption(
            "Active profile selection is available for Project and Run override scopes."
        )
        return

    ctrl = ProfileController()

    adapters = iter_all_profile_target_adapters()
    workflow_adapter = next((a for a in adapters if a.matches_type("workflow")), None)
    module_adapters = [a for a in adapters if a.matches_type("module")]

    if workflow_adapter is None:
        st.warning("Workflow profile support is not available.")
        return

    st.markdown("**Workflow Profile Activation**")
    if not ctrl.can_edit_activation_for_scope(workflow_adapter.target_id, scope):
        st.caption("Workflow profile activation is not editable in this scope.")
        return

    workflow_profiles = ctrl.list_profiles(workflow_adapter.target_id)
    workflow_current = draft_dot.get(workflow_adapter.activation_key, "default")
    if workflow_current not in workflow_profiles:
        workflow_profiles = [workflow_current] + workflow_profiles
    workflow_selected = st.selectbox(
        workflow_adapter.activation_label,
        options=workflow_profiles,
        index=workflow_profiles.index(workflow_current),
        key=f"{form_scope_key}_active_profile_workflow",
    )
    workflow_adapter.write_activation_value(value=workflow_selected, flat_map=draft_dot)

    st.markdown("**Module Profile Activation**")
    for adapter in module_adapters:
        if not ctrl.can_edit_activation_for_scope(adapter.target_id, scope):
            continue
        profiles = ctrl.list_profiles(adapter.target_id)
        current = draft_dot.get(adapter.activation_key, "default")
        if current not in profiles:
            profiles = [current] + profiles
        selected = st.selectbox(
            adapter.activation_label,
            options=profiles,
            index=profiles.index(current),
            key=f"{form_scope_key}_active_profile_{adapter.target_id}",
        )
        adapter.write_activation_value(value=selected, flat_map=draft_dot)


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
        "Precedence (highest to lowest): Environment, then Run override "
        "(or Draft override when no run is selected), then Project config, then Defaults."
    )
    st.caption(
        "Source labels currently report Draft override keys under the run-layer source model."
    )

    registry = build_registry()
    effective_dot = flatten(effective_config)
    categories = list(dict.fromkeys(meta.category for meta in registry.values()))

    for category in categories:
        keys = [k for k in effective_dot.keys() if k.startswith(f"{category}.")]
        if not keys:
            continue
        with st.expander(category.title(), expanded=False):
            for key in keys:
                value = effective_dot.get(key)
                source = sources.get(key, "default")
                st.write(f"`{key}`")
                st.caption(f"source: {source}")
                _render_effective_value(value)

    st.markdown("<div style='height: 1.25rem'></div>", unsafe_allow_html=True)

    dl_name = (
        "run_config_effective.json"
        if run_dir is not None
        else "workspace_config_effective.json"
    )
    with st.expander("View full JSON", expanded=False):
        st.download_button(
            "Download JSON",
            data=json.dumps(effective_config, indent=2),
            file_name=dl_name,
            mime="application/json",
        )
        st.code(json.dumps(effective_config, indent=2), language="json")

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
        base_config = _sanitize_scope_config(scope, draft or {})
    else:
        base_config = run_ov if run_dir is not None else {}

    current_run_cache = str(run_dir) if run_dir is not None else "__no_run__"
    if _should_reset_draft_state(
        st.session_state,
        scope=scope,
        current_run_cache=current_run_cache,
    ):
        st.session_state[_DRAFT_STATE_KEY] = copy.deepcopy(base_config)
        st.session_state[_SCOPE_CACHE_KEY] = scope
        st.session_state[_RUN_CACHE_KEY] = current_run_cache

    draft_config = _sanitize_scope_config(
        scope, st.session_state.get(_DRAFT_STATE_KEY) or {}
    )
    if draft_config != st.session_state.get(_DRAFT_STATE_KEY):
        st.session_state[_DRAFT_STATE_KEY] = copy.deepcopy(draft_config)
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
        common_keys = {item.key for item in COMMON_SETTINGS_SCHEMA}
        activation_keys = {
            adapter.activation_key for adapter in iter_all_profile_target_adapters()
        }
        editable_registry_keys = {
            key for key in registry.keys() if key not in activation_keys
        }
        surface_keys = common_keys - activation_keys
        st.markdown("**Common Settings**")
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
                    allowed_keys=surface_keys,
                )
                draft_dot.update(updated)

        st.divider()
        if scope in ("Project", "Run override"):
            st.markdown("**Active Profiles**")
            _render_active_profile_selectors(
                draft_dot=draft_dot,
                scope=scope,
                form_scope_key=form_scope_key,
            )

        st.divider()
        show_advanced = st.toggle(
            "Show advanced/raw settings editor",
            value=False,
            key="settings_config_show_advanced_editor",
        )
        if show_advanced:
            st.caption("Advanced editor exposes all registered keys. Use with care.")
            for category in categories:
                fields = [
                    meta for meta in registry.values() if meta.category == category
                ]
                if not fields:
                    continue
                with st.expander(f"{category.title()} (advanced)", expanded=False):
                    updated = render_config_form(
                        category=category,
                        fields=fields,
                        values=draft_dot,
                        show_only_changed=show_only_changed,
                        base_values=base_dot,
                        scope=f"{form_scope_key}_advanced",
                        allowed_keys=editable_registry_keys,
                    )
                    draft_dot.update(updated)

        draft_config = _sanitize_scope_config(scope, unflatten(draft_dot))
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
                    save_draft_override(_strip_activation_keys(draft_config))
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
