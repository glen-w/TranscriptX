"""
Group management page for TranscriptX Studio.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from transcriptx.web.cache_helpers import (
    cached_list_groups,
    clear_group_workspace_cache,
    get_cached_list_transcripts,
)
from transcriptx.web.services.group_service import GroupService
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_help, render_page_shell
from transcriptx.web.state import (
    SELECTBOX_PLACEHOLDER_GROUP,
    set_page_flash,
    try_page_toast,
)

_GROUPS_HELP = (
    "**Groups** bundle transcripts for batch or aggregate runs. "
    "Select a group below to rename, edit members, or open it in the subject panel."
)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_members(group_id: str) -> list:
    return GroupService.get_members(group_id)


def _clear_group_caches() -> None:
    clear_group_workspace_cache()
    _cached_get_members.clear()


def render_groups() -> None:
    render_page_shell(
        "Groups",
        "Create and manage transcript groups for aggregate analysis.",
        badges=None,
        actions=None,
    )

    transcripts = get_cached_list_transcripts()
    transcript_options = [str(m.path) for m in transcripts]
    transcript_labels = {str(m.path): m.base_name for m in transcripts}

    with st.expander("Create new group", expanded=False):
        name = st.text_input("Name", key="create_group_name")
        description = st.text_area("Description", key="create_group_description")
        selected_paths = st.multiselect(
            "Transcripts",
            options=transcript_options,
            format_func=lambda p: transcript_labels.get(p, Path(p).name),
            key="create_group_transcripts",
        )
        if st.button("Create group", type="primary", key="create_group_submit"):
            if not selected_paths:
                st.error("Select at least one transcript.")
            else:
                try:
                    group, created = GroupService.create_group_with_status(
                        name=(name or "").strip() or None,
                        group_type="group",
                        transcript_refs=selected_paths,
                        description=(description or "").strip() or None,
                        metadata=None,
                    )
                    _clear_group_caches()
                    if created:
                        set_page_flash("success", "Group created.")
                        try_page_toast("Group created.")
                    else:
                        set_page_flash(
                            "info", "Group already exists with those transcripts."
                        )
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    groups = cached_list_groups()
    if not groups:
        render_empty_state(
            "no_results_yet",
            "No groups yet",
            "Create a group from the expander above by selecting transcripts.",
            primary_action=("Open Library", "Library"),
            secondary_action=("Run Analysis", "Run Analysis"),
        )
        render_page_help(_GROUPS_HELP)
        return

    table_data = [
        {
            "Name": g.name or "Unnamed",
            "Member count": len(g.members),
            "Created": g.created_at or "—",
            "Updated": g.updated_at or "—",
            "Description": (g.description or "")[:60],
        }
        for g in groups
    ]
    st.dataframe(pd.DataFrame(table_data), width="stretch", hide_index=True)

    options = {g.group_id: g for g in groups}
    labels = {
        g.group_id: f"{g.name or 'Unnamed'} • {len(g.members)} transcripts"
        for g in groups
    }
    group_keys = list(options.keys())
    selected_id = st.selectbox(
        "Select group",
        [""] + group_keys,
        format_func=lambda key: (
            SELECTBOX_PLACEHOLDER_GROUP if key == "" else labels.get(key, key)
        ),
        index=0,
        key="groups_select_group",
    )
    if not selected_id:
        render_empty_state(
            "missing_prerequisite",
            "Select a group",
            "Pick a row from the table using the dropdown to view details.",
            primary_action=("Run Analysis", "Run Analysis"),
            secondary_action=None,
        )
        render_page_help(_GROUPS_HELP)
        return

    group = options[selected_id]

    st.subheader("Group details")
    st.write(f"**Name:** {group.name or '—'}")
    st.write(f"**UUID:** `{group.group_id}`")
    st.write(f"**Created:** {group.created_at or '—'}")
    st.write(f"**Updated:** {group.updated_at or '—'}")
    st.write(f"**Transcript count:** {len(group.members)}")

    members = _cached_get_members(group.group_id)
    if members:
        rows = [
            {"#": i + 1, "File name": m.file_name, "Path": m.file_path}
            for i, m in enumerate(members)
        ]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    rename_key = f"group_rename_input_{group.group_id}"
    with st.expander("Rename group"):
        new_name = st.text_input("Name", value=group.name or "", key=rename_key)
        if st.button("Update name", key=f"rename_btn_{group.group_id}"):
            new_name = (new_name or "").strip()
            if not new_name:
                st.error("Name cannot be empty.")
            elif new_name != (group.name or "").strip():
                try:
                    GroupService.rename_group(group.group_id, new_name)
                    _clear_group_caches()
                    st.session_state.pop(rename_key, None)
                    set_page_flash("success", "Group renamed.")
                    try_page_toast("Renamed.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    membership_key = f"group_membership_state_{group.group_id}"
    if membership_key not in st.session_state:
        st.session_state[membership_key] = [m.file_path for m in members]

    with st.expander("Edit membership"):
        working_paths: list[str] = st.session_state[membership_key]
        path_to_label = {str(m.path): m.base_name for m in transcripts}
        available_for_add = [p for p in transcript_options if p not in working_paths]
        if available_for_add:
            to_add = st.multiselect(
                "Add transcripts",
                options=available_for_add,
                format_func=lambda p: path_to_label.get(p, Path(p).name),
                key=f"membership_add_{group.group_id}",
            )
            if st.button("Add selected", key=f"membership_add_btn_{group.group_id}"):
                new_list = list(working_paths)
                for p in to_add:
                    if p not in new_list:
                        new_list.append(p)
                st.session_state[membership_key] = new_list
                st.rerun()

        st.multiselect(
            "Current transcripts",
            options=working_paths,
            default=working_paths,
            format_func=lambda p: path_to_label.get(p, Path(p).name),
            key=f"membership_current_{group.group_id}",
            disabled=True,
        )

        if st.button("Save membership", key=f"membership_save_{group.group_id}"):
            if not working_paths:
                st.error("Group must have at least one transcript.")
            else:
                try:
                    GroupService.update_membership(group.group_id, working_paths)
                    _clear_group_caches()
                    st.session_state.pop(membership_key, None)
                    set_page_flash("success", "Membership updated.")
                    try_page_toast("Membership updated.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        if st.button("Cancel", key=f"membership_cancel_{group.group_id}"):
            st.session_state.pop(membership_key, None)
            st.rerun()

    confirm_key = f"confirm_delete_group_{group.group_id}"
    if st.button("Delete group", type="secondary", key=f"delete_btn_{group.group_id}"):
        st.session_state[confirm_key] = True
        st.rerun()

    if st.session_state.get(confirm_key):
        st.warning(f"This will permanently delete '{group.name or group.group_id}'.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "Confirm delete", type="primary", key=f"confirm_del_{group.group_id}"
            ):
                GroupService.delete_group(group.group_id)
                _clear_group_caches()
                st.session_state.pop(confirm_key, None)
                st.session_state.pop(f"group_membership_state_{group.group_id}", None)
                set_page_flash("success", "Group deleted.")
                try_page_toast("Group deleted.")
                st.rerun()
        with col2:
            if st.button("Cancel", key=f"cancel_del_{group.group_id}"):
                st.session_state.pop(confirm_key, None)
                st.rerun()

    st.divider()
    if st.button("View group in subject panel", key=f"view_subject_{group.group_id}"):
        st.session_state["subject_type"] = "group"
        st.session_state["subject_id"] = group.group_id
        st.session_state["page"] = "Overview"
        st.rerun()
    render_page_help(_GROUPS_HELP)
