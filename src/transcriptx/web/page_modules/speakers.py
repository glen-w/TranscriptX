"""Speakers directory + detail for longitudinal speaker profiles."""

from __future__ import annotations

from uuid import uuid4

import streamlit as st

from transcriptx.core.speaker_profiles.aggregates import (
    aggregate_profile,
    list_profile_links,
    list_profiles,
    resolve_profile_redirect,
)
from transcriptx.core.speaker_profiles.errors import RepairRequiredError
from transcriptx.core.speaker_profiles.integrity import run_integrity_scan
from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.store_io import (
    profile_content_sha256,
)
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.speaker_profile_signals import consume_cache_invalidation_signal

_SPEAKERS_DESCRIPTION = (
    "Longitudinal speaker profiles linked across managed library transcripts. "
    "Headline totals exclude needs-review, missing-source, collision, and ignored appearances."
)


def _service() -> SpeakerProfileService:
    return SpeakerProfileService()


def render_speakers_page() -> None:
    render_page_shell("Speakers", _SPEAKERS_DESCRIPTION, badges=None, actions=None)
    root = speaker_profiles_dir()
    root.mkdir(parents=True, exist_ok=True)
    for sub in ("profiles", "links", "events", "operations"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    report = run_integrity_scan(root)
    if report.blocking_operations:
        st.error(
            "Repair required: incomplete speaker-profile operations are blocking "
            f"some records ({len(report.blocking_operations)}). "
            "Use Diagnostics or recover operations before editing."
        )

    items = list_profiles(root=root)
    active = [i for i in items if i.status == "active"]
    archived = [i for i in items if i.status == "archived"]
    merged = [i for i in items if i.status == "merged"]

    if not items:
        render_empty_state(
            "no_results_yet",
            "No speaker profiles yet",
            (
                "Create profiles from Speaker Identification on a managed library "
                "transcript (enable “Also link to longitudinal speaker profile”)."
            ),
            primary_action=("Speaker Identification", "Speaker ID"),
        )
        return

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Active", len(active))
    col_b.metric("Archived", len(archived))
    col_c.metric("Merged", len(merged))

    show_archived = st.checkbox("Show archived", value=False, key="speakers_show_archived")
    show_merged = st.checkbox("Show merged", value=False, key="speakers_show_merged")
    visible = list(active)
    if show_archived:
        visible.extend(archived)
    if show_merged:
        visible.extend(merged)

    if not visible:
        st.info("No profiles match the current filters.")
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
    selected = st.selectbox(
        "Select profile",
        options=options,
        format_func=lambda pid: labels.get(pid, pid),
        key="speakers_selected_profile",
    )
    if not selected:
        return

    _render_profile_detail(selected, root=root)


def _render_profile_detail(profile_id: str, *, root) -> None:
    try:
        resolved = resolve_profile_redirect(profile_id, root=root)
    except RepairRequiredError as exc:
        st.error(str(exc))
        return

    if resolved.profile_id != profile_id:
        st.info(
            f"Merged redirect: `{profile_id}` → **{resolved.display_name}** "
            f"(`{resolved.profile_id}`)."
        )

    if resolved.status == "archived":
        st.warning("This profile is archived. New links are not allowed.")

    # Check list item repair flag
    for item in list_profiles(root=root):
        if item.profile_id == resolved.profile_id and item.needs_repair:
            st.error("Intersecting incomplete operations block some reads for this profile.")
            break

    include_ignored = st.checkbox(
        "Include ignored appearances in headline totals",
        value=False,
        key=f"speakers_include_ignored_{resolved.profile_id}",
    )
    resolver = ManagedTranscriptResolver()
    links = list_profile_links(resolved.profile_id, root=root)
    agg = aggregate_profile(
        resolved, links, resolver=resolver, include_ignored=include_ignored
    )

    st.subheader(resolved.display_name)
    st.caption(
        f"Status: {resolved.status} · freshness `{agg.freshness_token[:12]}…` · "
        f"{agg.appearance_count} appearances"
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Headline words", agg.headline_words)
    m2.metric("Headline turns", agg.headline_turns)
    m3.metric("Headline duration (s)", f"{agg.headline_duration_seconds:.1f}")
    m4.metric(
        "Speaking share basis",
        agg.speaking_share_basis,
    )

    if agg.pending_review_count or agg.missing_source_count or agg.ignored_linked_count:
        st.markdown("#### Pending / excluded")
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Needs review", agg.pending_review_count)
        p2.metric("Missing source", agg.missing_source_count)
        p3.metric("Ignored linked", agg.ignored_linked_count)
        p4.metric("Collisions", agg.collision_count)

    st.markdown("#### Appearances")
    if not agg.appearances:
        st.info("No linked appearances.")
    else:
        rows = []
        for a in agg.appearances:
            rows.append(
                {
                    "date": a.appearance_date.isoformat() if a.appearance_date else "Unknown date",
                    "transcript": a.current_relpath or a.observed_transcript_relpath,
                    "speaker": a.local_speaker_key,
                    "flag": a.flag,
                    "words": a.metrics.words,
                    "turns": a.metrics.turns,
                    "duration": a.metrics.duration_seconds,
                    "speaking_share": a.speaking_share,
                }
            )
        st.dataframe(rows, width="stretch", hide_index=True)

    st.divider()
    st.markdown("#### Lifecycle")
    svc = _service()
    sha = profile_content_sha256(resolved.profile_id, root=root)
    c1, c2 = st.columns(2)
    with c1:
        if resolved.status == "active" and sha:
            if st.button("Archive profile", key=f"speakers_archive_{resolved.profile_id}"):
                try:
                    result = svc.archive_profile(
                        operation_idempotency_key=str(uuid4()),
                        profile_id=resolved.profile_id,
                        expected_content_sha256=sha,
                    )
                    consume_cache_invalidation_signal(result.cache_signal)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
    with c2:
        active_others = [
            i
            for i in list_profiles(root=root)
            if i.status == "active" and i.profile_id != resolved.profile_id
        ]
        if resolved.status == "active" and active_others and sha:
            target = st.selectbox(
                "Merge into",
                options=[i.profile_id for i in active_others],
                format_func=lambda pid: next(
                    (i.display_name for i in active_others if i.profile_id == pid), pid
                ),
                key=f"speakers_merge_target_{resolved.profile_id}",
            )
            if st.button("Merge into selected", key=f"speakers_merge_{resolved.profile_id}"):
                try:
                    result = svc.merge_profiles(
                        operation_idempotency_key=str(uuid4()),
                        source_profile_id=resolved.profile_id,
                        target_profile_id=target,
                        expected_source_sha256=sha,
                    )
                    consume_cache_invalidation_signal(result.cache_signal)
                    st.session_state["speakers_selected_profile"] = target
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
