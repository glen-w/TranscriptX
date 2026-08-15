"""
Profiles page - view and manage analysis profiles.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st

from transcriptx.app.controllers.profile_controller import ProfileController
from transcriptx.core.config import get_profile_target_adapter
from transcriptx.web.components.info_tooltip import widget_help


@st.cache_data(ttl=60, show_spinner=False)
def _cached_list_profiles(target_id: str) -> list[str]:
    return ProfileController().list_profiles(target_id)


def _profile_payload(
    ctrl: ProfileController, target_id: str, profile_name: str
) -> dict[str, Any]:
    if profile_name == "default":
        return {
            "name": profile_name,
            "module": target_id,
            "description": f"Virtual default profile for {target_id}",
            "config": {},
        }
    payload = ctrl.load_profile(target_id, profile_name)
    if payload:
        return payload
    return {"name": profile_name, "module": target_id, "description": "", "config": {}}


def _split_profile_names_for_display(
    profile_names: list[str],
) -> tuple[list[str], list[str]]:
    """Return (baseline_names, saved_names) with virtual default separated."""
    baseline = [name for name in profile_names if name == "default"]
    saved = [name for name in profile_names if name != "default"]
    return baseline, saved


def _create_copy_options(saved_profile_names: list[str]) -> list[str]:
    """Copy source options for create flow."""
    return saved_profile_names if saved_profile_names else ["default"]


def _render_guided_fields(
    target_id: str, current_config: dict[str, Any], widget_prefix: str
) -> dict[str, Any]:
    adapter = get_profile_target_adapter(target_id)
    if adapter is None or not adapter.guided_fields:
        st.caption("No guided fields configured for this target.")
        return {}
    updates: dict[str, Any] = {}
    for key in adapter.guided_fields:
        value = current_config.get(key)
        widget_key = f"{widget_prefix}_guided_{key}"
        if isinstance(value, bool):
            updates[key] = st.checkbox(key, value=value, key=widget_key)
        elif isinstance(value, int) and not isinstance(value, bool):
            updates[key] = st.number_input(key, value=value, step=1, key=widget_key)
        elif isinstance(value, float):
            updates[key] = st.number_input(key, value=float(value), key=widget_key)
        elif isinstance(value, list):
            raw = st.text_area(
                key,
                value=json.dumps(value),
                key=widget_key,
                height=80,
            )
            try:
                parsed = json.loads(raw)
                updates[key] = parsed
            except json.JSONDecodeError:
                updates[key] = value
        else:
            updates[key] = st.text_input(
                key, value="" if value is None else str(value), key=widget_key
            )
    return updates


def render_profiles_page() -> None:
    """Render the profiles page."""
    st.markdown(
        '<div class="main-header">Profiles</div>',
        unsafe_allow_html=True,
    )

    try:
        ctrl = ProfileController()
        targets = ctrl.list_supported_targets()
        target_choice = st.selectbox(
            "Profile target",
            options=[""] + targets,
            format_func=lambda t: (
                "Select a profile target"
                if t == ""
                else f"{(get_profile_target_adapter(t).type_badge if get_profile_target_adapter(t) else 'Profile')} · {t}"
            ),
            key="profiles_target",
            help=widget_help(
                (
                    "Module profiles tune one analysis module; workflow profiles tune "
                    "cross-cutting pipeline defaults. Activation is set under Settings → Configuration."
                )
            ),
        )
        if not target_choice:
            st.info("Select a supported profile target to manage profiles.")
            return

        profiles = _cached_list_profiles(target_choice)
        active = ctrl.get_active_profile(target_choice)
        st.metric("Profiles", len(profiles))
        st.caption(f"Active: {active}")
        st.caption(
            "Virtual default is selectable/inspectable but not editable, exportable, renameable, or deleteable."
        )

        st.subheader("Baseline")
        baseline_payload = _profile_payload(ctrl, target_choice, "default")
        st.caption("Virtual default is implicit and read-only.")
        with st.expander("Built-in default baseline", expanded=False):
            st.json(baseline_payload)

        _baseline_names, persisted_profiles = _split_profile_names_for_display(profiles)

        st.subheader("Saved profiles")
        st.caption(
            "Persisted profile artifacts only. Default baseline is not included here."
        )
        target_adapter = get_profile_target_adapter(target_choice)

        st.markdown("**Create profile**")
        create_name = st.text_input("New profile name", key="profiles_create_name")
        create_description = st.text_input(
            "Description (optional)", key="profiles_create_description"
        )
        create_mode = st.radio(
            "Create from",
            options=("baseline_default", "copy_saved_profile"),
            format_func=lambda mode: (
                "Baseline default"
                if mode == "baseline_default"
                else "Copy existing saved profile"
            ),
            key="profiles_create_mode",
        )
        copy_options = _create_copy_options(persisted_profiles)
        create_base = st.selectbox(
            "Copy settings from",
            options=copy_options,
            key="profiles_create_base",
            disabled=create_mode != "copy_saved_profile",
        )
        if st.button("Create profile", key="profiles_create_btn"):
            if not create_name.strip():
                st.error("Profile name is required.")
            elif create_name == "default":
                st.error("Use a non-default name.")
            else:
                base_profile_name = (
                    "default" if create_mode == "baseline_default" else create_base
                )
                base_payload = _profile_payload(ctrl, target_choice, base_profile_name)
                ok = ctrl.create_profile(
                    target_choice,
                    create_name.strip(),
                    base_payload.get("config", {}),
                    create_description.strip() or f"Profile for {target_choice}",
                )
                if ok:
                    st.success(f"Created profile `{create_name.strip()}`.")
                    _cached_list_profiles.clear()
                    st.rerun()
                else:
                    st.error("Failed to create profile.")

        if not persisted_profiles:
            st.info("No saved profiles yet.")

        st.subheader("Manage saved profiles")
        for profile_name in persisted_profiles:
            payload = _profile_payload(ctrl, target_choice, profile_name)
            with st.expander(profile_name, expanded=False):
                st.caption("Persisted profile")
                st.json(payload)

                desc_key = f"profiles_desc_{target_choice}_{profile_name}"
                current_desc = payload.get("description", "")
                updated_desc = st.text_input(
                    "Description", value=current_desc, key=desc_key
                )

                st.markdown("**Guided edit**")
                st.caption(
                    "Guided fields are a phase-1.5 supported subset for this target."
                )
                current_config = payload.get("config", {}) or {}
                guided_updates = _render_guided_fields(
                    target_choice, current_config, f"{target_choice}_{profile_name}"
                )
                merged_config = dict(current_config)
                merged_config.update(guided_updates)

                st.markdown("**Raw JSON fallback**")
                st.caption("Advanced: use raw JSON for unsupported fields.")
                raw_key = f"profiles_raw_{target_choice}_{profile_name}"
                raw_text = st.text_area(
                    "Profile config JSON",
                    value=json.dumps(merged_config, indent=2),
                    key=raw_key,
                    height=180,
                )
                parsed_raw = merged_config
                raw_error = None
                if target_adapter is None or target_adapter.allow_raw_json_fallback:
                    try:
                        parsed_raw = json.loads(raw_text)
                    except json.JSONDecodeError as exc:
                        parsed_raw = merged_config
                        raw_error = str(exc)
                        st.error(f"Invalid JSON: {raw_error}")

                col_save, col_rename, col_delete = st.columns(3)
                with col_save:
                    if st.button("Save", key=f"save_{target_choice}_{profile_name}"):
                        ok = ctrl.save_profile(
                            target_choice,
                            profile_name,
                            (
                                parsed_raw
                                if isinstance(parsed_raw, dict)
                                else merged_config
                            ),
                            updated_desc,
                        )
                        if ok:
                            st.success("Profile saved.")
                            _cached_list_profiles.clear()
                            st.rerun()
                        else:
                            st.error("Failed to save profile.")

                with col_rename:
                    new_name = st.text_input(
                        "Rename to",
                        key=f"rename_to_{target_choice}_{profile_name}",
                    )
                    if st.button(
                        "Rename", key=f"rename_{target_choice}_{profile_name}"
                    ):
                        if not new_name.strip():
                            st.error("New name is required.")
                        else:
                            ok = ctrl.rename_profile(
                                target_choice, profile_name, new_name.strip()
                            )
                            if ok:
                                st.success("Profile renamed.")
                                _cached_list_profiles.clear()
                                st.rerun()
                            else:
                                st.error("Failed to rename profile.")

                with col_delete:
                    if st.button(
                        "Delete", key=f"delete_{target_choice}_{profile_name}"
                    ):
                        ok = ctrl.delete_profile(target_choice, profile_name)
                        if ok:
                            st.success("Profile deleted.")
                            _cached_list_profiles.clear()
                            st.rerun()
                        else:
                            st.error("Failed to delete profile.")

                st.markdown("**Import/Export**")
                exp_path = st.text_input(
                    "Export path",
                    key=f"export_path_{target_choice}_{profile_name}",
                    value="",
                )
                if st.button("Export", key=f"export_{target_choice}_{profile_name}"):
                    if not exp_path.strip():
                        st.error("Provide an export path.")
                    else:
                        ok = ctrl.export_profile(target_choice, profile_name, exp_path)
                        (
                            st.success("Profile exported.")
                            if ok
                            else st.error("Export failed.")
                        )

                import_path = st.text_input(
                    "Import path",
                    key=f"import_path_{target_choice}_{profile_name}",
                    value="",
                )
                overwrite = st.checkbox(
                    "Overwrite if exists",
                    value=False,
                    key=f"overwrite_{target_choice}_{profile_name}",
                )
                if st.button(
                    "Import as this profile",
                    key=f"import_{target_choice}_{profile_name}",
                ):
                    if not import_path.strip():
                        st.error("Provide an import path.")
                    else:
                        ok = ctrl.import_profile(
                            target_choice,
                            profile_name,
                            Path(import_path.strip()),
                            overwrite=overwrite,
                        )
                        if ok:
                            st.success("Profile imported.")
                            _cached_list_profiles.clear()
                            st.rerun()
                        else:
                            st.error("Import failed.")
    except Exception as e:
        st.error(f"Could not load profiles: {e}")
