"""Speakers directory page, fragment, and overview."""

from __future__ import annotations

from typing import Mapping, Sequence

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.core.speaker_profiles.aggregates import (
    ProfileListItem,
)
from transcriptx.core.speaker_profiles.layout import (
    speaker_profiles_dir,
)
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.snapshot import (
    AggregationSnapshot,
)
from transcriptx.core.speaker_profiles.store_io import (
    ensure_layout,
)
from transcriptx.core.speaker_profiles.time_series import (
    build_directory_activity_chart,
)
from transcriptx.web.components.info_tooltip import widget_help
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.speaker_avatar import speaker_heading_with_avatar_html
from transcriptx.web.speaker_profile_signals import (
    INCLUDE_IGNORED_SESSION_KEY,
    SHOW_ARCHIVED_SESSION_KEY,
    SHOW_MERGED_SESSION_KEY,
)
from transcriptx.web.state import SELECTBOX_PLACEHOLDER_SPEAKER


from transcriptx.web.ui.speakers.support import (
    _SELECTED_KEY,
    _SEARCH_KEY,
    _SPEAKERS_DESCRIPTION,
    _directory_chart_frame,
    _gallery_meta,
    _get_speakers_aggregation_snapshot,
    _item_matches_search,
    _render_recovery_banners,
    _rerun_ui,
    _surname_sort_key,
)

from transcriptx.web.ui.speakers.detail import _render_profile_detail


def render_speakers_page() -> None:
    render_page_shell("Speakers", _SPEAKERS_DESCRIPTION, badges=None, actions=None)
    root = speaker_profiles_dir()
    root.mkdir(parents=True, exist_ok=True)
    ensure_layout(root)

    include_ignored = bool(st.session_state.get(INCLUDE_IGNORED_SESSION_KEY, False))

    snap = _get_speakers_aggregation_snapshot(
        root=root,
        include_ignored=include_ignored,
    )

    if snap.incomplete or not snap.integrity_ok:
        st.warning(
            "Speaker profile snapshot is incomplete "
            f"(integrity_ok={snap.integrity_ok}, incomplete={snap.incomplete}). "
            "Totals may omit blocked or corrupt records."
        )
    _render_recovery_banners(root)

    items = list(snap.listing)
    if not items:
        render_empty_state(
            "no_results_yet",
            "No speaker profiles yet",
            (
                "Create profiles from Speaker Identification on a managed library "
                "transcript: assign a name and choose Create new profile (or attach "
                "to an existing person). Then return here."
            ),
            primary_action=("Speaker Identification", "Speaker ID"),
        )
        return

    active = [i for i in items if i.status == "active"]
    archived = [i for i in items if i.status == "archived"]
    merged = [i for i in items if i.status == "merged"]
    show_archived = bool(st.session_state.get(SHOW_ARCHIVED_SESSION_KEY, False))
    show_merged = bool(st.session_state.get(SHOW_MERGED_SESSION_KEY, False))

    metric_specs: list[tuple[str, int]] = [("Active", len(active))]
    if show_archived:
        metric_specs.append(("Archived", len(archived)))
    if show_merged:
        metric_specs.append(("Merged", len(merged)))
    cols = st.columns(len(metric_specs))
    for col, (label, value) in zip(cols, metric_specs):
        col.metric(label, value)

    visible = list(active)
    if show_archived:
        visible.extend(archived)
    if show_merged:
        visible.extend(merged)
    visible.sort(key=_surname_sort_key)

    if not visible:
        st.info("No profiles match the current filters.")
        if st.session_state.get(_SELECTED_KEY):
            st.session_state[_SELECTED_KEY] = ""
        return

    labels = {
        i.profile_id: (
            f"{i.display_name} ({i.status}"
            f"{' · repair' if i.needs_repair else ''}"
            f" · {i.link_count} links)"
        )
        for i in visible
    }
    options = [i.profile_id for i in visible]
    selected_now = st.session_state.get(_SELECTED_KEY)
    if selected_now and selected_now not in options and selected_now != "":
        st.session_state[_SELECTED_KEY] = ""

    _speakers_browser_fragment(
        snap=snap,
        items=items,
        labels=labels,
        options=options,
        active_ids=[i.profile_id for i in active],
        include_ignored=include_ignored,
    )


@st.fragment
def _speakers_browser_fragment(
    *,
    snap: AggregationSnapshot,
    items: list[ProfileListItem],
    labels: Mapping[str, str],
    options: list[str],
    active_ids: list[str],
    include_ignored: bool,
) -> None:
    """Profile select + overview + detail; avoids snapshot rebuild on selection change."""
    visible_items = [i for i in items if i.profile_id in options]
    query = st.text_input(
        "Search people",
        value=str(st.session_state.get(_SEARCH_KEY) or ""),
        key=_SEARCH_KEY,
        placeholder="Name, alias, or notes…",
        help=widget_help("Filter the directory by display name, alias, or notes."),
    )
    notes_by_id = {
        p.profile_id: str(getattr(p, "notes", "") or "") for p in snap.profiles
    }
    matched = [
        i
        for i in visible_items
        if _item_matches_search(
            i, str(query or ""), extra=notes_by_id.get(i.profile_id, "")
        )
    ]
    if query and not matched:
        st.info("No profiles match that search.")
    elif matched:
        cols = st.columns(min(3, max(1, len(matched[:12]))))
        for idx, item in enumerate(matched[:12]):
            with cols[idx % len(cols)]:
                with st.container(border=True):
                    agg = snap.aggregates_by_profile.get(item.profile_id)
                    st.markdown(
                        speaker_heading_with_avatar_html(
                            item.display_name,
                            meta=_gallery_meta(item, agg),
                            accent=item.accent_color,
                            profile_id=item.profile_id,
                        ),
                        unsafe_allow_html=True,
                    )
                    if item.aliases:
                        st.caption("Also: " + ", ".join(item.aliases[:4]))
                    if st.button(
                        "Open",
                        key=f"speakers_open_card_{item.profile_id}",
                        icon=ic.OPEN_IN_NEW,
                    ):
                        st.session_state[_SELECTED_KEY] = item.profile_id
                        _rerun_ui()
        if len(matched) > 12:
            st.caption(f"Showing 12 of {len(matched)}. Narrow the search or use Jump.")

    selected = st.selectbox(
        "Jump to profile",
        options=[""] + options,
        format_func=lambda pid: (
            SELECTBOX_PLACEHOLDER_SPEAKER if pid == "" else labels.get(pid, pid)
        ),
        key=_SELECTED_KEY,
    )

    name_by_id = {i.profile_id: i.display_name for i in items}
    matched_ids = [i.profile_id for i in matched]
    chart_profile_ids = (
        [selected]
        if selected
        else [pid for pid in matched_ids if pid in set(active_ids)]
    )
    _render_directory_overview(
        snap,
        chart_profile_ids=chart_profile_ids,
        name_by_id=name_by_id,
        include_ignored=include_ignored,
    )

    if not selected:
        return

    profiles_by_id = {p.profile_id: p for p in snap.profiles}
    profile = profiles_by_id.get(selected)
    if profile is None:
        st.error(f"Selected profile `{selected}` is missing from the snapshot.")
        return

    if profile.status == "merged":
        _render_merged_readonly(profile, profiles_by_id=profiles_by_id)
        return

    listing_item = next((i for i in items if i.profile_id == selected), None)
    agg = snap.aggregates_by_profile.get(selected)
    appearances = snap.appearances_by_profile.get(selected, ())
    if agg is None:
        st.error("Aggregate missing for selected profile.")
        return

    _render_profile_detail(
        snap=snap,
        profile=profile,
        listing_item=listing_item,
        agg=agg,
        appearances=appearances,
        directory_items=items,
        include_ignored=include_ignored,
    )


def _render_directory_overview(
    snap: AggregationSnapshot,
    *,
    chart_profile_ids: Sequence[str],
    name_by_id: Mapping[str, str],
    include_ignored: bool,
) -> None:
    if not chart_profile_ids:
        return
    headline_words = {
        pid: int(agg.headline_words) for pid, agg in snap.aggregates_by_profile.items()
    }
    chart = build_directory_activity_chart(
        profile_rows=snap.appearances_by_profile,
        profile_headline_words=headline_words,
        active_profile_ids=list(chart_profile_ids),
        include_ignored=include_ignored,
        metric="words",
    )
    frame = _directory_chart_frame(chart, name_by_id=name_by_id)
    if frame.get("date"):
        st.bar_chart(frame, x="date", y=[c for c in frame if c != "date"])
    else:
        st.caption("No headline activity to chart yet.")


def _render_merged_readonly(
    profile: SpeakerProfileV1,
    *,
    profiles_by_id: Mapping[str, SpeakerProfileV1],
) -> None:
    target_id = profile.merged_into_profile_id
    target = profiles_by_id.get(target_id) if target_id else None
    target_name = (
        target.display_name if target is not None else (target_id or "unknown")
    )
    st.info(
        f"Merged redirect: `{profile.profile_id}` → **{target_name}** "
        f"(`{target_id}`)."
    )
    st.caption(
        "This merged profile is read-only. Open the target profile to edit, "
        "link, or change lifecycle."
    )
    if target_id and st.button(
        "Open target profile",
        key=f"speakers_open_merge_target_{profile.profile_id}",
        icon=ic.OPEN_IN_NEW,
        type="primary",
    ):
        st.session_state[_SELECTED_KEY] = target_id
        _rerun_ui()
