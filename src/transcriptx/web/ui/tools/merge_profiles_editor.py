"""Merge source profiles editor (System → Tools → Merge)."""

from __future__ import annotations

import streamlit as st

from transcriptx.core.audio.merge_profiles import (
    MergeSourceProfile,
    builtin_merge_source_profiles,
    load_merge_source_profiles,
    reset_builtin_profile,
    save_merge_source_profiles,
    validate_profiles_payload,
)
from transcriptx.web.components.info_tooltip import widget_help

_DRAFT_KEY = "audio_merge_profiles_draft"
_GEN_KEY = "audio_merge_profiles_gen"


def _seed_draft() -> list[dict]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "enabled": p.enabled,
            "builtin": p.builtin,
            "match_kind": p.match.kind,
            "families": ", ".join(p.match.families),
            "patterns": "\n".join(p.match.patterns),
            "builtin_rules": ", ".join(p.match.builtin_rules),
            "grouping_mode": p.grouping.mode,
            "same_day_days": int(p.grouping.same_day_days),
            "max_gap_hours": float(p.grouping.max_gap_hours),
            "priority": int(p.priority),
        }
        for p in load_merge_source_profiles()
    ]


def _draft_to_profiles(rows: list[dict]) -> list[MergeSourceProfile]:
    payload: list[dict] = []
    for row in rows:
        kind = str(row.get("match_kind") or "voice_note_family")
        families = [
            part.strip()
            for part in str(row.get("families") or "").split(",")
            if part.strip()
        ]
        patterns = [
            line.strip()
            for line in str(row.get("patterns") or "").splitlines()
            if line.strip()
        ]
        rules = [
            part.strip()
            for part in str(row.get("builtin_rules") or "").split(",")
            if part.strip()
        ]
        match: dict = {"kind": kind, "families": [], "patterns": [], "builtin_rules": []}
        if kind == "voice_note_family":
            match["families"] = families
        elif kind == "filename_regex":
            match["patterns"] = patterns
        else:
            match["builtin_rules"] = rules or [
                "timestamp_suffix",
                "part_suffix",
                "numeric_index",
                "duplicate_suffix",
            ]
        payload.append(
            {
                "id": str(row.get("id") or "").strip(),
                "name": str(row.get("name") or "").strip(),
                "enabled": bool(row.get("enabled", True)),
                "builtin": bool(row.get("builtin", False)),
                "match": match,
                "grouping": {
                    "mode": str(row.get("grouping_mode") or "time_window"),
                    "same_day_days": int(row.get("same_day_days") or 0),
                    "max_gap_hours": (
                        float(row["max_gap_hours"])
                        if row.get("max_gap_hours") is not None
                        else (20.0 / 60.0)
                    ),
                },
                "priority": int(row.get("priority") or 100),
            }
        )
    return validate_profiles_payload(payload)


def render_merge_profiles_editor() -> list[MergeSourceProfile]:
    """Render the profiles expander; return the effective profiles for detection."""
    if _DRAFT_KEY not in st.session_state:
        st.session_state[_DRAFT_KEY] = _seed_draft()
    if _GEN_KEY not in st.session_state:
        st.session_state[_GEN_KEY] = 0

    rows: list[dict] = st.session_state[_DRAFT_KEY]
    gen = int(st.session_state[_GEN_KEY])

    with st.expander("Merge source profiles", expanded=False):
        st.caption(
            "Configure how recordings are grouped for suggestions and auto-merge. "
            "Edits apply to detection immediately; Save writes "
            "`audio_merge_profiles.json`. "
            "Day and minutes sliders apply to time-window profiles "
            "(0 minutes = unlimited gap). Serial parts always merge by filename index. "
            "Examples of user settings: WhatsApp same day within 2 hours; "
            "Zoom full day; Telegram same day within 6 hours."
        )

        to_remove: list[int] = []
        for i, row in enumerate(rows):
            prefix = f"merge_prof_{gen}_{i}"
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 4, 1])
                with c1:
                    row["enabled"] = st.checkbox(
                        "On",
                        value=bool(row.get("enabled", True)),
                        key=f"{prefix}_en",
                    )
                with c2:
                    row["name"] = st.text_input(
                        "Name",
                        value=str(row.get("name") or ""),
                        key=f"{prefix}_name",
                    )
                with c3:
                    st.caption("builtin" if row.get("builtin") else "custom")

                row["match_kind"] = st.selectbox(
                    "Match",
                    options=["voice_note_family", "filename_regex", "builtin_serial"],
                    index=["voice_note_family", "filename_regex", "builtin_serial"].index(
                        row.get("match_kind") or "voice_note_family"
                    ),
                    key=f"{prefix}_kind",
                    help=widget_help(
                        "voice_note_family uses built-in brand parsers; "
                        "filename_regex uses your patterns; "
                        "builtin_serial uses part/index filename rules."
                    ),
                )
                kind = row["match_kind"]
                if kind == "voice_note_family":
                    row["families"] = st.text_input(
                        "Families (comma-separated)",
                        value=str(row.get("families") or ""),
                        key=f"{prefix}_families",
                    )
                elif kind == "filename_regex":
                    row["patterns"] = st.text_area(
                        "Regex patterns (one per line)",
                        value=str(row.get("patterns") or ""),
                        key=f"{prefix}_patterns",
                        height=80,
                    )
                else:
                    row["builtin_rules"] = st.text_input(
                        "Serial rules",
                        value=str(
                            row.get("builtin_rules")
                            or "timestamp_suffix, part_suffix, numeric_index, duplicate_suffix"
                        ),
                        key=f"{prefix}_rules",
                    )

                row["grouping_mode"] = st.selectbox(
                    "Grouping",
                    options=["time_window", "serial"],
                    index=0 if row.get("grouping_mode") != "serial" else 1,
                    key=f"{prefix}_mode",
                )
                if row["grouping_mode"] == "time_window":
                    dcol, hcol = st.columns(2)
                    with dcol:
                        row["same_day_days"] = st.slider(
                            "Day window",
                            min_value=0,
                            max_value=7,
                            value=int(row.get("same_day_days") or 0),
                            key=f"{prefix}_days",
                            help=widget_help(
                                "0 = any day; 1 = same calendar day; "
                                "N = within N days of the first file."
                            ),
                        )
                    with hcol:
                        # Edit as minutes so the 20-minute builtin default is exact.
                        raw_hours = row.get("max_gap_hours")
                        if raw_hours is None:
                            default_minutes = 20
                        else:
                            default_minutes = int(round(float(raw_hours) * 60))
                        minutes = st.slider(
                            "Within time period (minutes)",
                            min_value=0,
                            max_value=24 * 60,
                            value=max(0, min(24 * 60, default_minutes)),
                            step=1,
                            key=f"{prefix}_minutes",
                            help=widget_help(
                                "Max gap between consecutive files. "
                                "0 = unlimited (full day when day window is set). "
                                "Builtin voice-note default is 20 minutes."
                            ),
                        )
                        row["max_gap_hours"] = float(minutes) / 60.0
                row["priority"] = int(
                    st.number_input(
                        "Priority (lower wins)",
                        min_value=1,
                        max_value=999,
                        value=int(row.get("priority") or 100),
                        key=f"{prefix}_pri",
                    )
                )

                bcol1, bcol2 = st.columns(2)
                with bcol1:
                    if row.get("builtin") and st.button(
                        "Reset builtin",
                        key=f"{prefix}_reset",
                    ):
                        current = _draft_to_profiles(rows)
                        reset = reset_builtin_profile(current, row["id"])
                        st.session_state[_DRAFT_KEY] = [
                            {
                                "id": p.id,
                                "name": p.name,
                                "enabled": p.enabled,
                                "builtin": p.builtin,
                                "match_kind": p.match.kind,
                                "families": ", ".join(p.match.families),
                                "patterns": "\n".join(p.match.patterns),
                                "builtin_rules": ", ".join(p.match.builtin_rules),
                                "grouping_mode": p.grouping.mode,
                                "same_day_days": int(p.grouping.same_day_days),
                                "max_gap_hours": float(p.grouping.max_gap_hours),
                                "priority": int(p.priority),
                            }
                            for p in reset
                        ]
                        st.session_state[_GEN_KEY] = gen + 1
                        st.rerun()
                with bcol2:
                    if not row.get("builtin") and st.button(
                        "Delete",
                        key=f"{prefix}_del",
                    ):
                        to_remove.append(i)

        for i in reversed(to_remove):
            rows.pop(i)
            st.session_state[_GEN_KEY] = gen + 1
            st.rerun()

        acol, scol, rcol = st.columns(3)
        with acol:
            if st.button("Add profile", key="merge_prof_add"):
                rows.append(
                    {
                        "id": f"custom_{len(rows) + 1}",
                        "name": "Custom",
                        "enabled": True,
                        "builtin": False,
                        "match_kind": "filename_regex",
                        "families": "",
                        "patterns": "",
                        "builtin_rules": "",
                        "grouping_mode": "time_window",
                        "same_day_days": 1,
                        "max_gap_hours": 2.0,
                        "priority": 200,
                    }
                )
                st.session_state[_GEN_KEY] = gen + 1
                st.rerun()
        with scol:
            if st.button("Save profiles", type="primary", key="merge_prof_save"):
                try:
                    profiles = _draft_to_profiles(rows)
                    save_merge_source_profiles(profiles)
                    st.session_state[_DRAFT_KEY] = _seed_draft()
                    st.session_state[_GEN_KEY] = gen + 1
                    st.success("Merge source profiles saved.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not save profiles: {exc}")
        with rcol:
            if st.button("Reload defaults", key="merge_prof_reload_defaults"):
                st.session_state[_DRAFT_KEY] = [
                    {
                        "id": p.id,
                        "name": p.name,
                        "enabled": p.enabled,
                        "builtin": p.builtin,
                        "match_kind": p.match.kind,
                        "families": ", ".join(p.match.families),
                        "patterns": "\n".join(p.match.patterns),
                        "builtin_rules": ", ".join(p.match.builtin_rules),
                        "grouping_mode": p.grouping.mode,
                        "same_day_days": int(p.grouping.same_day_days),
                        "max_gap_hours": float(p.grouping.max_gap_hours),
                        "priority": int(p.priority),
                    }
                    for p in builtin_merge_source_profiles()
                ]
                st.session_state[_GEN_KEY] = gen + 1
                st.rerun()

    try:
        return _draft_to_profiles(rows)
    except Exception:
        return load_merge_source_profiles()
