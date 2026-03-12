"""
Group management page for TranscriptX Studio.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from transcriptx.web.cache_helpers import cached_list_groups, cached_list_transcripts
from transcriptx.web.services.group_service import GroupService  # type: ignore[import]


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_members(group_uuid: str) -> list:
    groups = cached_list_groups()
    group = next((g for g in groups if g.uuid == group_uuid), None)
    if not group:
        return []
    return GroupService.get_members(group)


def _clear_group_caches() -> None:
    """Clear group list and members caches after mutations."""
    cached_list_groups.clear()
    _cached_get_members.clear()


def render_groups() -> None:
    from transcriptx.core.utils.config import get_config

    if not getattr(get_config().database, "enabled", False):
        st.info(
            "This feature requires TranscriptX database mode. "
            "Enable it with `TRANSCRIPTX_DB_ENABLED=1`."
        )
        return

    st.markdown('<div class="main-header">Groups</div>', unsafe_allow_html=True)

    # ── Create Group form ─────────────────────────────────────────────────────
    with st.expander("Create new group", expanded=False):
        transcripts = cached_list_transcripts()
        name = st.text_input("Name", key="create_group_name")
        group_type = st.selectbox(
            "Type",
            ["merged_event"],
            index=0,
            key="create_group_type",
        )
        description = st.text_area("Description", key="create_group_description")
        if not transcripts:
            st.caption("No transcripts in library. Add transcript JSON files first.")
        else:
            transcript_options = [str(m.path) for m in transcripts]
            transcript_labels = [m.base_name for m in transcripts]
            selected_paths = st.multiselect(
                "Transcripts (order preserved)",
                options=range(len(transcript_options)),
                format_func=lambda i: (
                    transcript_labels[i] if i < len(transcript_labels) else ""
                ),
                key="create_group_transcripts",
            )
            if st.button("Create group", type="primary", key="create_group_submit"):
                if not selected_paths:
                    st.error("Select at least one transcript.")
                else:
                    refs = [transcript_options[i] for i in selected_paths]
                    name_val = (name or "").strip() or None
                    desc_val = (description or "").strip() or None
                    try:
                        group, created = GroupService.create_group_with_status(
                            name=name_val,
                            group_type=group_type,
                            transcript_refs=refs,
                            description=desc_val,
                            metadata=None,
                        )
                        _clear_group_caches()
                        if created:
                            st.success("Group created.")
                        else:
                            st.info(
                                "Group already exists with these transcripts (same order)."
                            )
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    groups = cached_list_groups()
    if not groups:
        st.info("No groups yet. Create a group above or via CLI/database tools.")
        return

    # ── Browse table (visual aid) ─────────────────────────────────────────────
    table_data = [
        {
            "Name": g.name or "Unnamed",
            "Type": g.type,
            "Transcript count": len(g.transcript_file_uuids or []),
            "Created": (
                g.created_at.strftime("%Y-%m-%d %H:%M") if g.created_at else "—"
            ),
            "Description": (lambda d: d[:50] + ("…" if len(d) > 50 else ""))(
                g.description or ""
            ),
        }
        for g in groups
    ]
    st.dataframe(
        pd.DataFrame(table_data),
        use_container_width=True,
        hide_index=True,
    )

    # ── Selection (source of truth) ───────────────────────────────────────────
    options = {g.uuid: g for g in groups}
    labels = {
        g.uuid: f"{g.name or 'Unnamed'} • {len(g.transcript_file_uuids or [])} transcripts"
        for g in groups
    }
    selected_id = st.selectbox(
        "Select group",
        list(options.keys()),
        format_func=lambda key: labels.get(key, key),
        key="groups_select_group",
    )
    group = options[selected_id]

    # ── Detail panel ─────────────────────────────────────────────────────────
    st.subheader("Group details")
    st.write(f"**Name:** {group.name or '—'}")
    st.write(f"**Type:** {group.type}")
    st.write(f"**UUID:** `{group.uuid}`")
    st.write(
        f"**Created:** {group.created_at.strftime('%Y-%m-%d %H:%M') if group.created_at else '—'}"
    )
    st.write(f"**Transcript count:** {len(group.transcript_file_uuids or [])}")

    members = _cached_get_members(group.uuid)
    if members:
        member_rows = [
            {
                "#": i + 1,
                "File name": getattr(m, "file_name", None)
                or (m.file_path.split("/")[-1] if m.file_path else "—"),
                "Duration": (
                    f"{m.duration_seconds:.1f}s"
                    if m.duration_seconds is not None
                    else "—"
                ),
                "Speakers": (
                    str(m.speaker_count) if m.speaker_count is not None else "—"
                ),
            }
            for i, m in enumerate(members)
        ]
        st.dataframe(
            pd.DataFrame(member_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("No transcript files resolved for this group.")

    # ── Rename ───────────────────────────────────────────────────────────────
    rename_key = f"group_rename_input_{group.uuid}"
    with st.expander("Rename group"):
        new_name = st.text_input("Name", value=group.name or "", key=rename_key)
        if st.button("Update name", key=f"rename_btn_{group.uuid}"):
            new_name = (new_name or "").strip()
            if not new_name:
                st.error("Name cannot be empty.")
            elif new_name != (group.name or "").strip():
                try:
                    GroupService.rename_group(group.uuid, new_name)
                    _clear_group_caches()
                    st.session_state.pop(rename_key, None)
                    st.success("Renamed.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    # ── Edit membership ──────────────────────────────────────────────────────
    membership_key = f"group_membership_state_{group.uuid}"
    if membership_key not in st.session_state:
        st.session_state[membership_key] = list(group.transcript_file_uuids or [])

    with st.expander("Edit membership"):
        working_uuids: list[str] = st.session_state[membership_key]
        uuid_to_label = {
            getattr(m, "uuid", None): (m.file_name or m.file_path or "")
            for m in members
            if getattr(m, "uuid", None)
        }

        for idx, uuid_val in enumerate(working_uuids):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                label = uuid_to_label.get(uuid_val) or (uuid_val[:12] + "…")
                st.text(f"{idx + 1}. {label}")
            with col2:
                if st.button(
                    "↑", key=f"member_up_{group.uuid}_{idx}", disabled=(idx == 0)
                ):
                    new_list = list(working_uuids)
                    new_list[idx], new_list[idx - 1] = new_list[idx - 1], new_list[idx]
                    st.session_state[membership_key] = new_list
                    st.rerun()
                if st.button(
                    "↓",
                    key=f"member_down_{group.uuid}_{idx}",
                    disabled=(idx >= len(working_uuids) - 1),
                ):
                    new_list = list(working_uuids)
                    new_list[idx], new_list[idx + 1] = new_list[idx + 1], new_list[idx]
                    st.session_state[membership_key] = new_list
                    st.rerun()
            with col3:
                if st.button("Remove", key=f"member_remove_{group.uuid}_{idx}"):
                    new_list = [u for i, u in enumerate(working_uuids) if i != idx]
                    st.session_state[membership_key] = new_list
                    st.rerun()

        available_for_add: list[tuple[str, str]] = []
        try:
            from transcriptx.database import get_session
            from transcriptx.database.repositories.transcript import (
                TranscriptFileRepository,
            )

            session = get_session()
            try:
                repo = TranscriptFileRepository(session)
                for m in cached_list_transcripts():
                    rec = repo.get_transcript_file_by_path(str(m.path))
                    if rec and rec.uuid not in working_uuids:
                        available_for_add.append((rec.uuid, m.base_name))
            finally:
                session.close()
        except Exception:
            pass

        if available_for_add:
            add_uuids = [u for u, _ in available_for_add]
            add_labels = {u: n for u, n in available_for_add}
            to_add = st.multiselect(
                "Add transcripts",
                options=add_uuids,
                format_func=lambda u: add_labels.get(u, u[:12]),
                key=f"membership_add_{group.uuid}",
            )
            if st.button("Add selected", key=f"membership_add_btn_{group.uuid}"):
                new_list = list(working_uuids)
                for u in to_add:
                    if u not in new_list:
                        new_list.append(u)
                st.session_state[membership_key] = new_list
                st.rerun()

        if st.button("Save membership", key=f"membership_save_{group.uuid}"):
            if not working_uuids:
                st.error("Group must have at least one transcript.")
            else:
                try:
                    GroupService.update_membership(group.uuid, working_uuids)
                    _clear_group_caches()
                    st.session_state.pop(membership_key, None)
                    st.success("Membership updated.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
        if st.button("Cancel", key=f"membership_cancel_{group.uuid}"):
            st.session_state.pop(membership_key, None)
            st.rerun()

    # ── Delete with confirmation ───────────────────────────────────────────────
    confirm_key = f"confirm_delete_group_{group.uuid}"
    if st.button("Delete group", type="secondary", key=f"delete_btn_{group.uuid}"):
        st.session_state[confirm_key] = True
        st.rerun()

    if st.session_state.get(confirm_key):
        st.warning(
            f"This will permanently delete '{group.name or group.uuid}' and its membership records."
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "Confirm delete", type="primary", key=f"confirm_del_{group.uuid}"
            ):
                GroupService.delete_group(group.uuid)
                _clear_group_caches()
                st.session_state.pop(confirm_key, None)
                st.session_state.pop(f"group_membership_state_{group.uuid}", None)
                st.success("Group deleted.")
                st.rerun()
        with col2:
            if st.button("Cancel", key=f"cancel_del_{group.uuid}"):
                st.session_state.pop(confirm_key, None)
                st.rerun()

    # ── View in subject panel ────────────────────────────────────────────────
    st.divider()
    if st.button("View group in subject panel", key=f"view_subject_{group.uuid}"):
        st.session_state["subject_type"] = "group"
        st.session_state["subject_id"] = group.uuid
        st.session_state["page"] = "Overview"
        st.rerun()
    st.caption(
        "To view group runs, select this group in the Subject picker or use the button above."
    )
