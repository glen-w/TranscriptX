"""Speakers directory + detail for longitudinal speaker profiles.

High-churn widgets run in ``@st.fragment`` so selectbox / form / confirm toggles do
not rebuild the aggregation snapshot (sidebar + full Speakers page). Commit
mutations still call full ``st.rerun()`` so the snapshot refreshes.
"""

from __future__ import annotations

import hashlib
import html
import json
from math import floor
from typing import Any, Mapping, Sequence
from uuid import uuid4

import streamlit as st

from transcriptx.core.speaker_profiles.accents import SPEAKER_ACCENTS
from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
    ProfileAggregate,
    ProfileListItem,
)
from transcriptx.core.speaker_profiles.discovery import discover_occurrences_for_resolved
from transcriptx.core.speaker_profiles.errors import StaleUpdateError
from transcriptx.core.speaker_profiles.integrity import run_integrity_scan
from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.resolver import ManagedTranscriptResolver
from transcriptx.core.speaker_profiles.service import SpeakerProfileService
from transcriptx.core.speaker_profiles.snapshot import (
    AggregationSnapshot,
    build_aggregation_snapshot,
)
from transcriptx.core.speaker_profiles.store_io import (
    ensure_layout,
    profile_content_sha256,
    read_live_link,
)
from transcriptx.core.speaker_profiles.analytics_pack import (
    build_profile_analytics_pack,
)
from transcriptx.core.speaker_profiles.interactions_pack import (
    build_profile_interactions_pack,
)
from transcriptx.core.speaker_profiles.locations_pack import (
    ProfileLocationMention,
    build_profile_locations_pack,
)
from transcriptx.core.speaker_profiles.longitudinal import AnalyticsGrain
from transcriptx.core.speaker_profiles.sentiment_pack import (
    build_profile_sentiment_pack,
)
from transcriptx.core.speaker_profiles.time_series import (
    DirectoryChartSeries,
    build_directory_activity_chart,
)
from transcriptx.utils.html_utils import wrap_tooltip_text
from transcriptx.web.navigation import (
    navigate_highlight_to_transcript,
    navigate_to_transcript_from_path,
)

_METHODOLOGY_CAPTIONS: dict[str, str] = {
    "share.duration_only": "Speaking share uses duration only (never turn share).",
    "wpm.weighted_period": "Speaking rate is words ÷ speaking minutes (weighted across sessions).",
    "turn_length.timing_valid_only": "Turn length uses timing-valid turns only (includes zero-duration).",
    "partial.available_while_reporting_missing": "Partial periods sum available timing and note missing evidence.",
    "partners.co_appearance_only": "Partners are co-appearances in shared sessions, not interaction proof.",
    "interactions.from_run_summary": (
        "Interaction and equity metrics come from the newest interactions run "
        "per linked appearance (speaker_summary), not from co-appearance alone."
    ),
    "sentiment.from_run_rows": (
        "Sentiment means come from the newest sentiment run per appearance "
        "(segment rows when available; summary fallback for compound)."
    ),
    "pack.phase16": "Trends are derived from confirmed profile links; not persisted as canonical data.",
    "grain.appearance_date": "Grouped by appearance date.",
    "grain.month": "Grouped by calendar month (YYYY-MM).",
    "grain.quarter": "Grouped by calendar quarter (YYYY-Qn).",
}

_EVIDENCE_CAPTIONS: dict[str, str] = {
    "no_timing_valid_turns": "No timing-valid turns in this period.",
    "denom_unavailable": "Speaking-share denominator unavailable.",
    "missing_timing:all": "No valid timing evidence in this period.",
}


def _evidence_caption(note: str | None) -> str:
    if not note:
        return ""
    if note in _EVIDENCE_CAPTIONS:
        return _EVIDENCE_CAPTIONS[note]
    if note.startswith("missing_timing:"):
        return f"Missing timing for {note.split(':', 1)[1]} sessions."
    if note.startswith("non_finite_metric:"):
        return f"Non-finite {note.split(':', 1)[1]} excluded."
    return note


def _methodology_lines(codes: Sequence[str]) -> list[str]:
    return [
        _METHODOLOGY_CAPTIONS[code]
        for code in codes
        if code in _METHODOLOGY_CAPTIONS and not code.startswith("partners.")
    ]


def _info_tooltip_html(
    lines: Sequence[str],
    *,
    control_id: str,
    aria_label: str,
    test_id: str = "tx-info-tooltip",
) -> str:
    """Build an ⓘ tooltip for multi-line help / notes."""
    if not lines:
        return ""
    tip_body = "<br>".join(html.escape(line) for line in lines)
    tip_id = html.escape(control_id, quote=True)
    aria = html.escape(aria_label, quote=True)
    test = html.escape(test_id, quote=True)
    return (
        f'<span class="tx-run-id-info tx-methodology-info" '
        f'data-testid="{test}">'
        f'<button type="button" class="tx-run-id-info-btn" tabindex="0" '
        f'aria-label="{aria}" aria-describedby="{tip_id}">ⓘ</button>'
        f'<span id="{tip_id}" class="tx-run-id-info-tip tx-methodology-info-tip" '
        f'role="tooltip">{tip_body}</span>'
        f"</span>"
    )


def _methodology_info_html(
    lines: Sequence[str],
    *,
    control_id: str,
) -> str:
    """Build an ⓘ tooltip for trends methodology notes."""
    return _info_tooltip_html(
        lines,
        control_id=control_id,
        aria_label="Trends methodology",
        test_id="tx-methodology-info",
    )


def _section_heading_with_info_html(title: str, tip_html: str) -> str:
    return (
        '<div class="tx-section-info-heading">'
        f"<h4>{html.escape(title)}</h4>"
        f"{tip_html}"
        "</div>"
    )

from transcriptx.core.utils.paths import PATHS
from transcriptx.core.utils.speaker import parse_speaker_name
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.speaker_avatar import speaker_heading_with_avatar_html
from transcriptx.web.speaker_profile_signals import (
    INCLUDE_IGNORED_SESSION_KEY,
    SHOW_ARCHIVED_SESSION_KEY,
    SHOW_MERGED_SESSION_KEY,
    consume_cache_invalidation_signal,
)
from transcriptx.web.state import SELECTBOX_PLACEHOLDER_SPEAKER

_SPEAKERS_DESCRIPTION = (
    "Longitudinal speaker profiles linked across managed library transcripts. "
    "Headline totals exclude needs-review, missing-source, collision, and ignored appearances "
    "(toggle inclusion under Settings → Speakers)."
)

_SELECTED_KEY = "speakers_selected_profile"


def _service() -> SpeakerProfileService:
    return SpeakerProfileService()


def _idempotency_key(action: str, payload_dict: Mapping[str, Any]) -> str:
    """Session key bound to a canonical payload hash; regenerates when payload changes."""
    digest = _payload_digest(payload_dict)
    store_key = f"speakers_idem_{action}"
    entry = st.session_state.get(store_key)
    if (
        isinstance(entry, dict)
        and entry.get("payload_hash") == digest
        and entry.get("key")
    ):
        return str(entry["key"])
    key = str(uuid4())
    st.session_state[store_key] = {"payload_hash": digest, "key": key}
    return key


def _payload_digest(payload_dict: Mapping[str, Any]) -> str:
    blob = json.dumps(
        dict(payload_dict),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _clear_idempotency(action: str) -> None:
    st.session_state.pop(f"speakers_idem_{action}", None)


def _rerun_ui() -> None:
    """Rerun only the nearest fragment (preview / confirm toggles)."""
    st.rerun(scope="fragment")


def _surname_sort_key(item: ProfileListItem) -> tuple[str, str, str, str]:
    first_name, surname = parse_speaker_name(item.display_name)
    return (
        (surname or first_name or "").casefold(),
        (first_name or "").casefold(),
        item.display_name.casefold(),
        item.profile_id,
    )


def _directory_chart_frame(
    chart: DirectoryChartSeries,
    *,
    name_by_id: Mapping[str, str],
) -> dict[str, list[Any]]:
    labels: list[str] = []
    seen: set[str] = set()
    for points in chart.series_by_key.values():
        for point in points:
            if point.display_label not in seen:
                seen.add(point.display_label)
                labels.append(point.display_label)
    frame: dict[str, list[Any]] = {"date": labels}
    for key, points in chart.series_by_key.items():
        col = "Other" if key == "Other" else name_by_id.get(key, key)
        by_label = {p.display_label: (p.value if p.value is not None else 0.0) for p in points}
        frame[col] = [by_label.get(lab, 0.0) for lab in labels]
    return frame


def _render_recovery_banners(root) -> None:
    report = run_integrity_scan(root)
    if report.ok and not report.blocking_operations and not report.blocking_details:
        return

    st.error(
        "Repair required: incomplete or corrupt speaker-profile state is blocking "
        "some records. Review details below or use Diagnostics."
    )
    if (
        report.corrupt_profiles
        or report.corrupt_links
        or report.corrupt_events
        or report.corrupt_operations
    ):
        st.warning(
            "Corrupt records: "
            f"profiles={len(report.corrupt_profiles)}, "
            f"links={len(report.corrupt_links)}, "
            f"events={len(report.corrupt_events)}, "
            f"operations={len(report.corrupt_operations)}."
        )

    svc = _service()
    for detail in report.blocking_details:
        with st.container(border=True):
            st.markdown(f"**Operation** `{detail.operation_id}`")
            st.caption(
                f"recovery_class=`{detail.recovery_class}` · phase=`{detail.phase}`"
            )
            if detail.affected_relpaths:
                st.code("\n".join(detail.affected_relpaths), language=None)
            else:
                st.caption("No affected paths listed.")
            if st.button(
                "Attempt safe recovery",
                key=f"speakers_recover_{detail.operation_id}",
                type="primary",
            ):
                try:
                    result = svc.recover_operation(detail.operation_id)
                    consume_cache_invalidation_signal(result.cache_signal)
                    rc = result.report.recovery_class
                    if rc == "complete":
                        st.success(f"Recovery complete for `{detail.operation_id}`.")
                    elif rc == "proven_aborted":
                        st.info(
                            f"Operation `{detail.operation_id}` proven aborted "
                            "(never applied)."
                        )
                    elif rc == "needs_repair" or result.report.blocking:
                        st.warning(
                            f"Operation `{detail.operation_id}` still needs_repair "
                            f"(class=`{rc}`)."
                        )
                    else:
                        st.warning(
                            f"Recovery finished with class `{rc}` for "
                            f"`{detail.operation_id}`."
                        )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Recovery failed: {exc}")


def render_speakers_page() -> None:
    render_page_shell("Speakers", _SPEAKERS_DESCRIPTION, badges=None, actions=None)
    root = speaker_profiles_dir()
    root.mkdir(parents=True, exist_ok=True)
    ensure_layout(root)

    include_ignored = bool(st.session_state.get(INCLUDE_IGNORED_SESSION_KEY, False))

    snap = build_aggregation_snapshot(
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
                "transcript (enable “Also link to longitudinal speaker profile”)."
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
    selected = st.selectbox(
        "Select profile",
        options=[""] + options,
        format_func=lambda pid: (
            SELECTBOX_PLACEHOLDER_SPEAKER if pid == "" else labels.get(pid, pid)
        ),
        key=_SELECTED_KEY,
    )

    name_by_id = {i.profile_id: i.display_name for i in items}
    chart_profile_ids = [selected] if selected else list(active_ids)
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
        pid: int(agg.headline_words)
        for pid, agg in snap.aggregates_by_profile.items()
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
    target_name = target.display_name if target is not None else (target_id or "unknown")
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
        type="primary",
    ):
        st.session_state[_SELECTED_KEY] = target_id
        _rerun_ui()


def _render_profile_detail(
    *,
    snap: AggregationSnapshot,
    profile: SpeakerProfileV1,
    listing_item: ProfileListItem | None,
    agg: ProfileAggregate,
    appearances: tuple[AppearanceRow, ...],
    directory_items: list[ProfileListItem],
    include_ignored: bool,
) -> None:
    profile_blocked = profile.profile_id in snap.blocked_profile_ids
    if profile.status == "archived":
        st.warning("This profile is archived. New links are not allowed.")
    if listing_item and listing_item.needs_repair:
        st.error("Intersecting incomplete operations block some reads for this profile.")
    if profile_blocked:
        st.error("Mutations are disabled while this profile intersects a blocking operation.")

    meta = (
        f"{profile.status} · freshness `{agg.freshness_token[:12]}…` · "
        f"{agg.appearance_count:,} appearances"
    )
    avatar_bytes = None
    try:
        avatar_bytes = _service().read_avatar_bytes(profile.profile_id)
    except Exception:
        avatar_bytes = None
    st.markdown(
        speaker_heading_with_avatar_html(
            profile.display_name,
            meta=meta,
            accent=profile.accent_color,
            image_bytes=avatar_bytes,
            content_type=profile.avatar_content_type or "image/webp",
        ),
        unsafe_allow_html=True,
    )

    ignored_clause = (
        "Ignored links are included."
        if include_ignored
        else "Ignored links are excluded."
    )
    eligibility_help = (
        "Sums only eligible linked appearances: excludes needs-review, "
        f"missing-source, collision, and repair-required. {ignored_clause}"
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Words",
        f"{agg.headline_words:,}",
        help=f"Total words spoken across eligible appearances. {eligibility_help}",
    )
    m2.metric(
        "Turns",
        f"{agg.headline_turns:,}",
        help=f"Total speaking turns across eligible appearances. {eligibility_help}",
    )
    m3.metric(
        "Duration (h)",
        f"{agg.headline_duration_seconds / 3600:,.1f}",
        help=(
            "Total speaking duration across eligible appearances, in hours. "
            f"{eligibility_help}"
        ),
    )
    m4.metric(
        "Appearances",
        f"{agg.headline_appearance_count:,}",
        help=(
            "Linked appearances included in the word, turn, and duration totals. "
            f"{eligibility_help} The header count includes all linked appearances."
        ),
    )

    if (
        agg.pending_review_count
        or agg.missing_source_count
        or agg.ignored_linked_count
        or agg.collision_count
        or agg.repair_required_count
    ):
        st.markdown("#### Pending / excluded")
        p1, p2, p3, p4, p5 = st.columns(5)
        p1.metric("Needs review", agg.pending_review_count)
        p2.metric("Missing source", agg.missing_source_count)
        p3.metric("Ignored linked", agg.ignored_linked_count)
        p4.metric("Collisions", agg.collision_count)
        p5.metric("Repair required", agg.repair_required_count)

    _render_detail_charts(
        snap,
        profile.profile_id,
        appearances,
        include_ignored=include_ignored,
    )

    _render_locations_map(
        snap,
        profile,
        include_ignored=include_ignored,
    )
    _render_interactions_equity(
        snap,
        profile,
        include_ignored=include_ignored,
    )
    _render_sentiment_trends(
        snap,
        profile,
        include_ignored=include_ignored,
    )

    links_by_id = {
        link.link_id: link for link in snap.links_by_profile.get(profile.profile_id, ())
    }
    _render_appearances_table(
        snap=snap,
        profile=profile,
        appearances=appearances,
        links_by_id=links_by_id,
        profile_blocked=profile_blocked,
    )

    if not profile_blocked and profile.status == "active":
        _render_voice_controls(snap=snap, profile=profile)

    if not profile_blocked:
        _render_edit_form(profile, root=snap.root)
        if profile.status == "active":
            _render_link_another(snap=snap, profile=profile)

    _render_lifecycle(
        snap=snap,
        profile=profile,
        directory_items=directory_items,
        profile_blocked=profile_blocked,
    )


@st.fragment
def _render_voice_controls(
    *,
    snap: AggregationSnapshot,
    profile: SpeakerProfileV1,
) -> None:
    """Promote / wipe profile voice evidence when ActivationBarrier allows."""
    try:
        from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
        from transcriptx.core.speaker_profiles.voice.inventory import (
            list_samples_for_profile,
        )
        from transcriptx.core.speaker_profiles.voice.promote import VoicePromotionService
        from transcriptx.core.speaker_profiles.voice.wipe import VoiceWipeService
    except Exception:
        return

    status = ActivationBarrier(snap.root).status()
    with st.expander("Voice evidence", expanded=False):
        if not status.allowed:
            st.caption(
                "Local voice matching is not active "
                f"({status.block_reason or 'unavailable'})."
            )
            return

        samples = list_samples_for_profile(profile.profile_id, root=snap.root)
        eligible = sum(1 for s in samples if s.eligibility_state == "eligible")
        ineligible = sum(1 for s in samples if s.eligibility_state != "eligible")
        from transcriptx.core.speaker_profiles.voice.operator import VoiceOperatorStore

        bootstrap_max_links = (
            VoiceOperatorStore(snap.root).read().bootstrap_max_links
        )
        st.caption(
            f"{len(samples)} sample(s) · {eligible} eligible · "
            f"{ineligible} need promotion · enrol cap {bootstrap_max_links} "
            "link(s) (Settings → Speakers). Stored under "
            f"`{snap.root / 'voice'}` — survives Docker rebuild; "
            "cleared only by revoke or Delete voice evidence."
        )
        enrol_action = f"voice_bootstrap_{profile.profile_id}"
        if st.button(
            "Enrol trusted voice from confirmed links",
            key=f"spk_voice_bootstrap_{profile.profile_id}",
            help=(
                "Explicit bootstrap: extracts and embeds voice from this profile's "
                "confirmed links (up to the Settings → Speakers enrol link cap). "
                "Privacy opt-in alone does not enrol anything."
            ),
        ):
            try:
                from transcriptx.services.speaker_profiles.voice_facade import (
                    SpeakerIdVoiceFacade,
                )

                result = SpeakerIdVoiceFacade(root=snap.root).bootstrap_enrol_profile(
                    operation_idempotency_key=_idempotency_key(
                        enrol_action, {"profile_id": profile.profile_id}
                    ),
                    profile_id=profile.profile_id,
                )
                _clear_idempotency(enrol_action)
                st.success(
                    f"Enrolled {result.links_enrolled}/{result.links_attempted} link(s); "
                    f"{len(result.sample_ids)} sample(s)."
                )
                for item in result.per_link:
                    if item.outcome != "Enrolled":
                        st.caption(
                            f"{item.link_file_key}: {item.outcome} — {item.detail or ''}"
                        )
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

        for sample in samples:
            if sample.eligibility_state == "eligible":
                continue
            cols = st.columns([4, 1])
            cols[0].write(
                f"`{sample.sample_id[:12]}…` · {sample.trust_level} · "
                f"{sample.local_speaker_key}"
            )
            promo_action = f"voice_promote_{sample.sample_id}"
            if cols[1].button(
                "Promote",
                key=f"spk_voice_promote_{sample.sample_id}",
            ):
                try:
                    VoicePromotionService(root=snap.root).promote_sample(
                        operation_idempotency_key=_idempotency_key(
                            promo_action, {"sample_id": sample.sample_id}
                        ),
                        sample_id=sample.sample_id,
                    )
                    _clear_idempotency(promo_action)
                    st.success("Sample promoted to trusted reference.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        wipe_action = f"voice_wipe_profile_{profile.profile_id}"
        if samples and st.button(
            "Delete voice evidence for this profile",
            key=f"spk_voice_wipe_{profile.profile_id}",
        ):
            try:
                VoiceWipeService(root=snap.root).wipe_profile_voice(
                    operation_idempotency_key=_idempotency_key(
                        wipe_action, {"profile_id": profile.profile_id}
                    ),
                    profile_id=profile.profile_id,
                )
                _clear_idempotency(wipe_action)
                st.warning("Profile voice artefacts deleted.")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


@st.fragment
def _render_detail_charts(
    snap: AggregationSnapshot,
    profile_id: str,
    appearances: tuple[AppearanceRow, ...],
    *,
    include_ignored: bool,
) -> None:
    """High-churn Trends + partners UI; fragment avoids snapshot rebuild on chart toggle."""
    with st.expander("Trends", expanded=False):
        tip_slot = st.empty()
        c_chart, c_stat, c_grain, c_all = st.columns([2, 1, 1, 1])
        chart_choice = c_chart.selectbox(
            "Chart",
            [
                "Speaking time",
                "Speaking share",
                "Words & turns",
                "Turn length",
                "Speaking rate",
            ],
            key=f"spk_trend_chart_{profile_id}",
        )
        # Secondary series/stat filter for charts that expose more than one metric.
        secondary_options: dict[str, tuple[str, list[str]]] = {
            "Turn length": ("Stat", ["Mean", "Median"]),
            "Words & turns": ("Series", ["Words", "Turns"]),
        }
        if chart_choice in secondary_options:
            secondary_label, options = secondary_options[chart_choice]
            secondary_choice = c_stat.selectbox(
                secondary_label,
                options,
                key=f"spk_trend_secondary_{profile_id}_{chart_choice}",
            )
        else:
            c_stat.empty()
            secondary_choice = None
        grain_label = c_grain.selectbox(
            "Grain",
            ["By date", "Month", "Quarter"],
            key=f"spk_trend_grain_{profile_id}",
        )
        include_all = c_all.checkbox(
            "Show all-appearances series",
            value=False,
            key=f"spk_trend_all_{profile_id}",
        )
        grain_map: dict[str, AnalyticsGrain] = {
            "By date": "appearance_date",
            "Month": "month",
            "Quarter": "quarter",
        }
        grain = grain_map[grain_label]
        try:
            pack = build_profile_analytics_pack(
                snap,
                profile_id,
                grain=grain,
                include_ignored=include_ignored,
                include_all_series=include_all,
            )
        except Exception as exc:
            st.error(f"Could not build analytics pack: {exc}")
            return

        series_map = {
            "Speaking time": ("speaking_minutes", "Speaking minutes"),
            "Speaking share": ("speaking_share", "Speaking share"),
            "Speaking rate": ("speaking_rate_wpm", "Words per minute"),
        }
        # Resolve the single series shown for multi-metric charts.
        selected_attr: str | None = None
        selected_ylabel = ""
        selected_value_key = "value"
        if chart_choice == "Turn length":
            if secondary_choice == "Median":
                selected_attr = "turn_length_median"
                selected_ylabel = "Median turn length (seconds)"
                selected_value_key = "median_seconds"
            else:
                selected_attr = "turn_length_avg"
                selected_ylabel = "Mean turn length (seconds)"
                selected_value_key = "avg_seconds"
        elif chart_choice == "Words & turns":
            if secondary_choice == "Turns":
                selected_attr = "turns"
                selected_ylabel = "Turns"
                selected_value_key = "turns"
            else:
                selected_attr = "words"
                selected_ylabel = "Words"
                selected_value_key = "words"
        elif chart_choice in series_map:
            selected_attr, selected_ylabel = series_map[chart_choice]

        methodology = _methodology_lines(pack.methodology_codes)
        if selected_ylabel:
            methodology = [*methodology, f"Headline — {selected_ylabel}"]
        tip_html = _methodology_info_html(
            methodology,
            control_id=f"spk-meth-{profile_id}",
        )
        if tip_html:
            tip_slot.markdown(
                f'<div class="tx-section-info-heading">{tip_html}</div>',
                unsafe_allow_html=True,
            )

        if not appearances:
            st.caption("No linked appearances to chart yet.")
        else:
            bundle = pack.headline
            assert selected_attr is not None
            points = getattr(bundle, selected_attr)
            data = _series_points_frame(points, selected_value_key)
            st.caption(f"{selected_ylabel} (headline)")
            if data:
                st.bar_chart(data, x="period", y=selected_value_key)
            else:
                st.caption("No headline points.")
            unavail = sum(1 for p in points if p.availability == "unavailable")
            partial = sum(1 for p in points if p.availability == "partial")
            if unavail or partial:
                st.caption(
                    f"Availability: {partial} partial, "
                    f"{unavail} unavailable period(s)."
                )
            if include_all and pack.all_appearances is not None:
                all_points = getattr(pack.all_appearances, selected_attr)
                adata = _series_points_frame(all_points, selected_value_key)
                st.caption(f"All appearances — {selected_ylabel}")
                if adata:
                    st.bar_chart(adata, x="period", y=selected_value_key)

            if points:
                rows = [
                    {
                        "period": p.display_label,
                        "value": p.value,
                        "availability": p.availability,
                        "evidence": _evidence_caption(p.evidence_note),
                        "n_turns": p.n_valid_turns,
                        "transcripts": len(p.managed_transcript_ids),
                    }
                    for p in points
                ]
                st.dataframe(rows, hide_index=True, width="stretch")

    partners_tip = _info_tooltip_html(
        [_METHODOLOGY_CAPTIONS["partners.co_appearance_only"]],
        control_id=f"spk-partners-{profile_id}",
        aria_label="Conversation partners notes",
        test_id="tx-partners-info",
    )
    with st.expander("Conversation partners", expanded=False):
        if partners_tip:
            st.markdown(
                f'<div class="tx-section-info-heading">{partners_tip}</div>',
                unsafe_allow_html=True,
            )
        if not pack.partners:
            st.info("No co-appearances yet.")
            return
        partner_rows = [
            {
                "Partner": p.display_name,
                "Status": p.status,
                "Shared sessions": p.shared_transcript_count,
                "Your speaking minutes": p.shared_speaking_minutes,
                "Availability": p.availability,
                "Evidence": _evidence_caption(p.evidence_note),
            }
            for p in pack.partners
        ]
        st.dataframe(partner_rows, hide_index=True, width="stretch")
        if pack.partners_remainder_count:
            st.caption(f"+{pack.partners_remainder_count} more partners not shown.")


def _mention_label(mention: ProfileLocationMention, index: int) -> str:
    date_label = (
        mention.appearance_date.isoformat()
        if mention.appearance_date is not None
        else "Unknown date"
    )
    return f"{index + 1}. {mention.name} · {date_label} · {mention.transcript_label}"


def _build_locations_folium_html(
    mentions: tuple[ProfileLocationMention, ...],
    *,
    speaker_name: str,
) -> str | None:
    """Return Folium map HTML, or None when [maps] extra is unavailable."""
    try:
        from transcriptx.core.utils.lazy_imports import get_folium

        folium = get_folium()
    except ImportError:
        return None

    fmap = folium.Map(zoom_start=2)
    # Slight jitter when multiple mentions share coordinates.
    seen: dict[tuple[float, float], int] = {}
    for mention in mentions:
        key = (round(mention.lat, 5), round(mention.lon, 5))
        n = seen.get(key, 0)
        seen[key] = n + 1
        lat = mention.lat + (0.00015 * n)
        lon = mention.lon + (0.00015 * n)
        folium.Marker(
            [lat, lon],
            popup=folium.Popup(
                wrap_tooltip_text(
                    mention.name,
                    speaker=speaker_name,
                    sentence=mention.sentence or mention.name,
                ),
                max_width=320,
            ),
        ).add_to(fmap)
    return fmap._repr_html_()


@st.fragment
def _render_locations_map(
    snap: AggregationSnapshot,
    profile: SpeakerProfileV1,
    *,
    include_ignored: bool,
) -> None:
    """Collapsed NER geo map + jump controls for the selected profile."""
    with st.expander("Locations", expanded=False):
        agg = snap.aggregates_by_profile.get(profile.profile_id)
        freshness = agg.freshness_token if agg is not None else ""
        cache_key = f"spk_loc_pack_{profile.profile_id}_{freshness}_{include_ignored}"
        pack = st.session_state.get(cache_key)
        if pack is None:
            try:
                pack = build_profile_locations_pack(
                    snap,
                    profile.profile_id,
                    include_ignored=include_ignored,
                )
            except Exception as exc:
                st.error(f"Could not load location mentions: {exc}")
                return
            st.session_state[cache_key] = pack

        if pack.status == "empty" or not pack.mentions:
            st.info("No geocoded location mentions for this profile yet.")
            if pack.appearances_without_ner:
                st.caption(
                    f"{pack.appearances_without_ner} appearance(s) had no usable NER "
                    "location data."
                )
            if pack.unresolved_mentions:
                st.caption(
                    f"{pack.unresolved_mentions} mention(s) skipped (could not resolve "
                    "segment for jump)."
                )
            return

        map_html = _build_locations_folium_html(
            pack.mentions, speaker_name=profile.display_name
        )
        if map_html:
            st.components.v1.html(map_html, height=400)
        else:
            st.caption(
                "Map preview unavailable (install optional `[maps]` extra for Folium)."
            )

        labels = [_mention_label(m, i) for i, m in enumerate(pack.mentions)]
        selected = st.selectbox(
            "Mention",
            options=list(range(len(pack.mentions))),
            format_func=lambda i: labels[i],
            key=f"spk_loc_select_{profile.profile_id}",
        )
        mention = pack.mentions[int(selected)]
        if mention.sentence:
            st.caption(mention.sentence)
        if st.button(
            "Open in transcript",
            key=f"spk_loc_jump_{profile.profile_id}",
            type="primary",
        ):
            navigate_highlight_to_transcript(
                session_slug=mention.session_slug,
                run_id=mention.run_id,
                segment_index=mention.segment_index,
                start_time=mention.start_time,
                highlight_query=(mention.sentence or mention.name)[:120],
            )

        notes: list[str] = []
        if pack.appearances_without_ner:
            notes.append(
                f"{pack.appearances_without_ner} appearance(s) without NER locations"
            )
        if pack.unresolved_mentions:
            notes.append(
                f"{pack.unresolved_mentions} mention(s) skipped (unresolved segment)"
            )
        if notes:
            st.caption(" · ".join(notes))


@st.fragment
def _render_interactions_equity(
    snap: AggregationSnapshot,
    profile: SpeakerProfileV1,
    *,
    include_ignored: bool,
) -> None:
    """Collapsed interactions / equity table for the selected profile."""
    with st.expander("Interactions & equity", expanded=False):
        tip = _info_tooltip_html(
            [_METHODOLOGY_CAPTIONS["interactions.from_run_summary"]],
            control_id=f"spk-ix-{profile.profile_id}",
            aria_label="Interactions methodology notes",
            test_id="tx-interactions-info",
        )
        if tip:
            st.markdown(
                f'<div class="tx-section-info-heading">{tip}</div>',
                unsafe_allow_html=True,
            )

        agg = snap.aggregates_by_profile.get(profile.profile_id)
        freshness = agg.freshness_token if agg is not None else ""
        cache_key = f"spk_ix_pack_{profile.profile_id}_{freshness}_{include_ignored}"
        pack = st.session_state.get(cache_key)
        if pack is None:
            try:
                pack = build_profile_interactions_pack(
                    snap,
                    profile.profile_id,
                    include_ignored=include_ignored,
                )
            except Exception as exc:
                st.error(f"Could not load interactions metrics: {exc}")
                return
            st.session_state[cache_key] = pack

        if pack.status == "empty" or not pack.appearances:
            st.info("No interactions run data for this profile yet.")
            if pack.appearances_without_interactions:
                st.caption(
                    f"{pack.appearances_without_interactions} appearance(s) had no "
                    "usable interactions speaker summary."
                )
            return

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Interruptions out", f"{pack.total_interruptions_initiated:,}")
        m2.metric("Interruptions in", f"{pack.total_interruptions_received:,}")
        m3.metric("Responses out", f"{pack.total_responses_initiated:,}")
        m4.metric("Responses in", f"{pack.total_responses_received:,}")
        e1, e2 = st.columns(2)
        e1.metric(
            "Mean dominance",
            (
                f"{pack.mean_dominance_score:.2f}"
                if pack.mean_dominance_score is not None
                else "—"
            ),
        )
        e2.metric(
            "Mean floor share",
            (
                f"{pack.mean_floor_share:.0%}"
                if pack.mean_floor_share is not None
                else "—"
            ),
        )

        table_rows = [
            {
                "Date": (
                    a.appearance_date.isoformat()
                    if a.appearance_date is not None
                    else "Unknown"
                ),
                "Transcript": a.transcript_label,
                "Interruptions out": a.interruptions_initiated,
                "Interruptions in": a.interruptions_received,
                "Responses out": a.responses_initiated,
                "Responses in": a.responses_received,
                "Dominance": a.dominance_score,
                "Floor share": a.floor_share,
                "Interrupt asymmetry": a.interruption_asymmetry,
                "Response latency (s)": a.response_latency_mean,
            }
            for a in pack.appearances
        ]
        st.dataframe(table_rows, hide_index=True, width="stretch")

        chart_rows = [
            {
                "period": (
                    a.appearance_date.isoformat()
                    if a.appearance_date is not None
                    else "Unknown"
                ),
                "floor_share": a.floor_share,
                "dominance": a.dominance_score,
            }
            for a in pack.appearances
            if a.floor_share is not None or a.dominance_score is not None
        ]
        if chart_rows:
            st.caption("Floor share / dominance by appearance")
            st.bar_chart(
                chart_rows,
                x="period",
                y=["floor_share", "dominance"],
            )

        if pack.appearances_without_interactions:
            st.caption(
                f"{pack.appearances_without_interactions} appearance(s) without "
                "interactions data"
            )


@st.fragment
def _render_sentiment_trends(
    snap: AggregationSnapshot,
    profile: SpeakerProfileV1,
    *,
    include_ignored: bool,
) -> None:
    """Collapsed sentiment means for the selected profile."""
    with st.expander("Sentiment", expanded=False):
        tip = _info_tooltip_html(
            [_METHODOLOGY_CAPTIONS["sentiment.from_run_rows"]],
            control_id=f"spk-sent-{profile.profile_id}",
            aria_label="Sentiment methodology notes",
            test_id="tx-sentiment-info",
        )
        if tip:
            st.markdown(
                f'<div class="tx-section-info-heading">{tip}</div>',
                unsafe_allow_html=True,
            )

        agg = snap.aggregates_by_profile.get(profile.profile_id)
        freshness = agg.freshness_token if agg is not None else ""
        cache_key = f"spk_sent_pack_{profile.profile_id}_{freshness}_{include_ignored}"
        pack = st.session_state.get(cache_key)
        if pack is None:
            try:
                pack = build_profile_sentiment_pack(
                    snap,
                    profile.profile_id,
                    include_ignored=include_ignored,
                )
            except Exception as exc:
                st.error(f"Could not load sentiment metrics: {exc}")
                return
            st.session_state[cache_key] = pack

        if pack.status == "empty" or not pack.appearances:
            st.info("No sentiment run data for this profile yet.")
            if pack.appearances_without_sentiment:
                st.caption(
                    f"{pack.appearances_without_sentiment} appearance(s) had no "
                    "usable sentiment artifact."
                )
            return

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(
            "Compound mean",
            f"{pack.compound_mean:.3f}" if pack.compound_mean is not None else "—",
        )
        m2.metric(
            "Pos mean",
            f"{pack.pos_mean:.3f}" if pack.pos_mean is not None else "—",
        )
        m3.metric(
            "Neu mean",
            f"{pack.neu_mean:.3f}" if pack.neu_mean is not None else "—",
        )
        m4.metric(
            "Neg mean",
            f"{pack.neg_mean:.3f}" if pack.neg_mean is not None else "—",
        )
        if (
            pack.positive_share is not None
            or pack.neutral_share is not None
            or pack.negative_share is not None
        ):
            s1, s2, s3 = st.columns(3)
            s1.metric(
                "Positive share",
                (
                    f"{pack.positive_share:.0%}"
                    if pack.positive_share is not None
                    else "—"
                ),
            )
            s2.metric(
                "Neutral share",
                (
                    f"{pack.neutral_share:.0%}"
                    if pack.neutral_share is not None
                    else "—"
                ),
            )
            s3.metric(
                "Negative share",
                (
                    f"{pack.negative_share:.0%}"
                    if pack.negative_share is not None
                    else "—"
                ),
            )

        chart_rows = [
            {
                "period": (
                    a.appearance_date.isoformat()
                    if a.appearance_date is not None
                    else "Unknown"
                ),
                "compound": a.compound_mean,
            }
            for a in pack.appearances
            if a.compound_mean is not None
        ]
        if chart_rows:
            st.caption("Compound sentiment by appearance")
            st.bar_chart(chart_rows, x="period", y="compound")

        table_rows = [
            {
                "Date": (
                    a.appearance_date.isoformat()
                    if a.appearance_date is not None
                    else "Unknown"
                ),
                "Transcript": a.transcript_label,
                "Segments": a.segment_count,
                "Compound": a.compound_mean,
                "Pos": a.pos_mean,
                "Neu": a.neu_mean,
                "Neg": a.neg_mean,
                "Pos / Neu / Neg counts": (
                    f"{a.positive_count}/{a.neutral_count}/{a.negative_count}"
                ),
            }
            for a in pack.appearances
        ]
        st.dataframe(table_rows, hide_index=True, width="stretch")

        if pack.appearances_without_sentiment:
            st.caption(
                f"{pack.appearances_without_sentiment} appearance(s) without "
                "sentiment data"
            )


def _series_points_frame(points: tuple[Any, ...], value_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in points:
        if p.value is None:
            continue
        rows.append({"period": p.display_label, value_key: float(p.value)})
    return rows


def _open_transcript(snap: AggregationSnapshot, row: AppearanceRow) -> None:
    path = None
    bundle = snap.bundles.get(row.managed_transcript_id)
    if bundle is not None and bundle.resolved is not None:
        path = bundle.resolved.transcript_path
    elif row.current_relpath:
        path = PATHS.transcripts_dir / row.current_relpath
    elif row.observed_transcript_relpath:
        path = PATHS.transcripts_dir / row.observed_transcript_relpath
    if path is None:
        st.error("Could not resolve transcript path for this appearance.")
        return
    # Transcript requires subject + run_id; path-only navigation silently
    # falls back to Home via the page access gate.
    if not navigate_to_transcript_from_path(path):
        st.error(
            "Could not open transcript: no analysis run is linked for this "
            "appearance. Open it from Library or run analysis first."
        )


@st.fragment
def _render_appearances_table(
    *,
    snap: AggregationSnapshot,
    profile: SpeakerProfileV1,
    appearances: tuple[AppearanceRow, ...],
    links_by_id: Mapping[str, Any],
    profile_blocked: bool,
) -> None:
    with st.expander("Appearances", expanded=False):
        if not appearances:
            st.info("No linked appearances.")
            return

        svc = _service()
        for row in appearances:
            link_blocked = row.link_file_key in snap.blocked_link_keys
            mutate_disabled = profile_blocked or link_blocked
            with st.container(border=True):
                date_label = (
                    row.appearance_date.isoformat()
                    if row.appearance_date is not None
                    else "Unknown date"
                )
                transcript_label = row.current_relpath or row.observed_transcript_relpath
                share = (
                    f"{floor(row.speaking_share * 100)}%"
                    if row.speaking_share is not None
                    else "—"
                )
                st.markdown(
                    f"**{date_label}** · `{transcript_label}` · "
                    f"flag=`{row.flag}` · words={row.metrics.words:,} · "
                    f"turns={row.metrics.turns:,} · share={share}"
                )
                cols = st.columns([1, 1, 1, 2])
                with cols[0]:
                    if st.button(
                        "Open transcript",
                        key=f"speakers_open_tx_{row.link_id}",
                    ):
                        _open_transcript(snap, row)

                confirm_unlink = f"speakers_confirm_unlink_{row.link_id}"
                with cols[1]:
                    if mutate_disabled:
                        st.caption("Unlink blocked")
                    elif st.session_state.get(confirm_unlink):
                        st.caption("Confirm unlink?")
                        u1, u2 = st.columns(2)
                        with u1:
                            if st.button(
                                "Confirm",
                                key=f"speakers_unlink_yes_{row.link_id}",
                                type="primary",
                            ):
                                payload = {
                                    "managed_transcript_id": row.managed_transcript_id,
                                    "local_speaker_key": row.local_speaker_key,
                                    "expected_link_id": row.link_id,
                                }
                                try:
                                    result = svc.unlink(
                                        operation_idempotency_key=_idempotency_key(
                                            f"unlink_{row.link_id}", payload
                                        ),
                                        managed_transcript_id=row.managed_transcript_id,
                                        local_speaker_key=row.local_speaker_key,
                                        expected_link_id=row.link_id,
                                    )
                                    consume_cache_invalidation_signal(result.cache_signal)
                                    _clear_idempotency(f"unlink_{row.link_id}")
                                    st.session_state.pop(confirm_unlink, None)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(str(exc))
                        with u2:
                            if st.button(
                                "Cancel",
                                key=f"speakers_unlink_no_{row.link_id}",
                            ):
                                _clear_idempotency(f"unlink_{row.link_id}")
                                st.session_state.pop(confirm_unlink, None)
                                _rerun_ui()
                    elif st.button(
                        "Unlink",
                        key=f"speakers_unlink_{row.link_id}",
                        disabled=mutate_disabled,
                    ):
                        st.session_state[confirm_unlink] = True
                        _rerun_ui()

                with cols[2]:
                    if row.flag != "needs_review":
                        st.caption("")
                    elif mutate_disabled:
                        st.caption("Accept blocked")
                    else:
                        link = links_by_id.get(row.link_id)
                        expected_fp = (
                            link.occurrence_fingerprint if link is not None else None
                        )
                        confirm_fp = f"speakers_confirm_fp_{row.link_id}"
                        if st.session_state.get(confirm_fp):
                            st.caption("Accept fingerprint?")
                            f1, f2 = st.columns(2)
                            with f1:
                                if st.button(
                                    "Confirm",
                                    key=f"speakers_fp_yes_{row.link_id}",
                                    type="primary",
                                ):
                                    payload = {
                                        "managed_transcript_id": row.managed_transcript_id,
                                        "local_speaker_key": row.local_speaker_key,
                                        "expected_link_id": row.link_id,
                                        "expected_fingerprint": expected_fp,
                                    }
                                    try:
                                        result = svc.supersede_link_fingerprint(
                                            operation_idempotency_key=_idempotency_key(
                                                f"fp_{row.link_id}", payload
                                            ),
                                            managed_transcript_id=row.managed_transcript_id,
                                            local_speaker_key=row.local_speaker_key,
                                            expected_link_id=row.link_id,
                                            expected_fingerprint=expected_fp,
                                        )
                                        consume_cache_invalidation_signal(
                                            result.cache_signal
                                        )
                                        _clear_idempotency(f"fp_{row.link_id}")
                                        st.session_state.pop(confirm_fp, None)
                                        st.rerun()
                                    except Exception as exc:
                                        st.error(str(exc))
                            with f2:
                                if st.button(
                                    "Cancel",
                                    key=f"speakers_fp_no_{row.link_id}",
                                ):
                                    _clear_idempotency(f"fp_{row.link_id}")
                                    st.session_state.pop(confirm_fp, None)
                                    _rerun_ui()
                        elif st.button(
                            "Accept fingerprint",
                            key=f"speakers_fp_{row.link_id}",
                            disabled=mutate_disabled or expected_fp is None,
                        ):
                            st.session_state[confirm_fp] = True
                            _rerun_ui()


@st.fragment
def _render_edit_form(profile: SpeakerProfileV1, *, root) -> None:
    with st.expander("Edit profile", expanded=False):
        form_prefix = f"speakers_edit_{profile.profile_id}"
        display_name = st.text_input(
            "Display name",
            value=profile.display_name,
            key=f"{form_prefix}_display_name",
        )
        aliases_text = st.text_area(
            "Aliases (one per line)",
            value="\n".join(profile.aliases),
            key=f"{form_prefix}_aliases",
        )
        notes = st.text_area(
            "Notes",
            value=profile.notes or "",
            key=f"{form_prefix}_notes",
        )
        clear_notes = st.checkbox(
            "Clear notes",
            value=False,
            key=f"{form_prefix}_clear_notes",
        )

        clear_accent = st.checkbox(
            "Auto from name (clear stored accent)",
            value=False,
            key=f"{form_prefix}_clear_accent",
            help="Clears accent_color so display falls back to the name-hash palette.",
        )
        default_accent = profile.accent_color or SPEAKER_ACCENTS[0]
        chosen_accent: str | None = None
        with st.popover("Choose colour"):
            chosen_accent = st.color_picker(
                "Accent colour",
                value=default_accent if str(default_accent).startswith("#") else SPEAKER_ACCENTS[0],
                key=f"{form_prefix}_color_picker",
                disabled=clear_accent,
            )
            st.caption("Quick palette")
            chip_cols = st.columns(len(SPEAKER_ACCENTS))
            for idx, accent in enumerate(SPEAKER_ACCENTS):
                with chip_cols[idx]:
                    if st.button(
                        accent,
                        key=f"{form_prefix}_chip_{accent}",
                        help=accent,
                        disabled=clear_accent,
                    ):
                        st.session_state[f"{form_prefix}_color_picker"] = accent
                        _rerun_ui()

        st.markdown("##### Photo")
        upload = st.file_uploader(
            "Upload photo (JPEG/PNG/WebP, max 2 MB)",
            type=["jpg", "jpeg", "png", "webp"],
            key=f"{form_prefix}_avatar_upload",
        )
        clear_avatar = st.checkbox(
            "Remove photo",
            value=False,
            key=f"{form_prefix}_clear_avatar",
            help="Clears the stored avatar; chip falls back to initials + accent.",
        )
        if st.button(
            "Save photo changes",
            key=f"{form_prefix}_avatar_save",
            disabled=upload is None and not clear_avatar,
        ):
            try:
                sha_avatar = profile_content_sha256(profile.profile_id, root=root)
                if not sha_avatar:
                    raise RuntimeError("Could not read profile content hash")
                if clear_avatar:
                    result = _service().clear_avatar(
                        operation_idempotency_key=_idempotency_key(
                            f"clear_avatar_{profile.profile_id}",
                            {"profile_id": profile.profile_id, "sha": sha_avatar},
                        ),
                        profile_id=profile.profile_id,
                        expected_content_sha256=sha_avatar,
                    )
                else:
                    assert upload is not None
                    result = _service().set_avatar(
                        operation_idempotency_key=_idempotency_key(
                            f"set_avatar_{profile.profile_id}",
                            {
                                "profile_id": profile.profile_id,
                                "sha": sha_avatar,
                                "name": upload.name,
                                "size": upload.size,
                            },
                        ),
                        profile_id=profile.profile_id,
                        expected_content_sha256=sha_avatar,
                        image_bytes=upload.getvalue(),
                    )
                consume_cache_invalidation_signal(result.cache_signal)
                _clear_idempotency(f"set_avatar_{profile.profile_id}")
                _clear_idempotency(f"clear_avatar_{profile.profile_id}")
                st.success("Photo updated.")
                st.rerun()
            except StaleUpdateError as exc:
                st.error(f"Stale update — refresh and try again. {exc}")
            except Exception as exc:
                st.error(str(exc))

        sha = profile_content_sha256(profile.profile_id, root=root)
        if not sha:
            st.error("Could not read profile content hash; edit disabled.")
            return

        aliases = [line.strip() for line in aliases_text.splitlines() if line.strip()]
        picker_value = st.session_state.get(f"{form_prefix}_color_picker", chosen_accent)
        payload = {
            "profile_id": profile.profile_id,
            "expected_content_sha256": sha,
            "display_name": display_name,
            "aliases": aliases,
            "notes": None if clear_notes else notes,
            "clear_notes": clear_notes,
            "accent_color": None if clear_accent else picker_value,
            "clear_accent": clear_accent,
        }

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Save changes", key=f"{form_prefix}_save", type="primary"):
                try:
                    result = _service().update_profile(
                        operation_idempotency_key=_idempotency_key(
                            f"update_{profile.profile_id}", payload
                        ),
                        profile_id=profile.profile_id,
                        expected_content_sha256=sha,
                        display_name=display_name,
                        aliases=aliases,
                        notes=None if clear_notes else (notes or None),
                        clear_notes=clear_notes,
                        accent_color=None if clear_accent else picker_value,
                        clear_accent=clear_accent,
                    )
                    consume_cache_invalidation_signal(result.cache_signal)
                    _clear_idempotency(f"update_{profile.profile_id}")
                    st.success("Profile updated.")
                    st.rerun()
                except StaleUpdateError as exc:
                    st.error(f"Stale update — refresh and try again. {exc}")
                except Exception as exc:
                    st.error(str(exc))
        with c2:
            if st.button("Cancel edit", key=f"{form_prefix}_cancel"):
                _clear_idempotency(f"update_{profile.profile_id}")
                for suffix in (
                    "display_name",
                    "aliases",
                    "notes",
                    "clear_notes",
                    "clear_accent",
                    "color_picker",
                ):
                    st.session_state.pop(f"{form_prefix}_{suffix}", None)
                _rerun_ui()


@st.fragment
def _render_link_another(
    *,
    snap: AggregationSnapshot,
    profile: SpeakerProfileV1,
) -> None:
    with st.expander("Link another occurrence", expanded=False):
        if profile.profile_id in snap.blocked_profile_ids:
            st.caption("Linking disabled while this profile is blocked.")
            return

        resolver = ManagedTranscriptResolver()
        try:
            admitted = resolver.list_admitted()
        except Exception as exc:
            st.error(f"Could not list managed transcripts: {exc}")
            return
        if not admitted:
            st.caption("No admitted managed transcripts.")
            return

        labels = {
            r.managed_transcript_id: f"{r.current_relpath} ({r.managed_transcript_id[:8]}…)"
            for r in admitted
        }
        options = [r.managed_transcript_id for r in admitted]
        chosen_tid = st.selectbox(
            "Managed transcript",
            options=[""] + options,
            format_func=lambda tid: (
                "— Select a transcript —" if tid == "" else labels.get(tid, tid)
            ),
            key=f"speakers_link_tid_{profile.profile_id}",
        )
        if not chosen_tid:
            return

        resolved = next(
            (r for r in admitted if r.managed_transcript_id == chosen_tid), None
        )
        if resolved is None:
            st.error("Selected transcript is no longer admitted.")
            return

        try:
            occurrences = discover_occurrences_for_resolved(resolved)
        except Exception as exc:
            st.error(f"Occurrence discovery failed: {exc}")
            return
        if not occurrences:
            st.info("No speaker occurrences in this transcript.")
            return

        occ_labels = {
            o.local_speaker_key: (
                f"{o.local_speaker_key} ({o.segment_count} segs"
                f"{' · collision' if o.collision else ''})"
            )
            for o in occurrences
        }
        chosen_key = st.selectbox(
            "Local speaker key",
            options=[""] + [o.local_speaker_key for o in occurrences],
            format_func=lambda key: (
                "— Select occurrence —" if key == "" else occ_labels.get(key, key)
            ),
            key=f"speakers_link_key_{profile.profile_id}",
        )
        if not chosen_key:
            return

        existing = read_live_link(
            next(o.link_file_key for o in occurrences if o.local_speaker_key == chosen_key),
            root=snap.root,
        )
        svc = _service()
        if existing is None:
            if st.button(
                "Link to this profile",
                key=f"speakers_link_existing_{profile.profile_id}",
                type="primary",
            ):
                payload = {
                    "managed_transcript_id": chosen_tid,
                    "local_speaker_key": chosen_key,
                    "profile_id": profile.profile_id,
                }
                try:
                    result = svc.link_existing_profile(
                        operation_idempotency_key=_idempotency_key(
                            f"link_{profile.profile_id}", payload
                        ),
                        managed_transcript_id=chosen_tid,
                        local_speaker_key=chosen_key,
                        profile_id=profile.profile_id,
                    )
                    consume_cache_invalidation_signal(result.cache_signal)
                    _clear_idempotency(f"link_{profile.profile_id}")
                    st.success("Occurrence linked.")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            return

        if existing.profile_id == profile.profile_id:
            st.info("This occurrence is already linked to this profile.")
            return

        owner_name = next(
            (
                p.display_name
                for p in snap.profiles
                if p.profile_id == existing.profile_id
            ),
            existing.profile_id,
        )
        st.warning(
            f"Occurrence is linked to **{owner_name}** (`{existing.profile_id}`). "
            "Relink to move it to this profile."
        )
        confirm_key = f"speakers_confirm_relink_{profile.profile_id}_{chosen_key}"
        if st.session_state.get(confirm_key):
            r1, r2 = st.columns(2)
            with r1:
                if st.button(
                    "Confirm relink",
                    key=f"speakers_relink_yes_{profile.profile_id}",
                    type="primary",
                ):
                    payload = {
                        "managed_transcript_id": chosen_tid,
                        "local_speaker_key": chosen_key,
                        "profile_id": profile.profile_id,
                        "expected_owner_profile_id": existing.profile_id,
                        "expected_link_id": existing.link_id,
                    }
                    try:
                        result = svc.relink(
                            operation_idempotency_key=_idempotency_key(
                                f"relink_{profile.profile_id}", payload
                            ),
                            managed_transcript_id=chosen_tid,
                            local_speaker_key=chosen_key,
                            profile_id=profile.profile_id,
                            expected_link_id=existing.link_id,
                            expected_owner_profile_id=existing.profile_id,
                        )
                        consume_cache_invalidation_signal(result.cache_signal)
                        _clear_idempotency(f"relink_{profile.profile_id}")
                        st.session_state.pop(confirm_key, None)
                        st.success("Occurrence relinked.")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            with r2:
                if st.button(
                    "Cancel",
                    key=f"speakers_relink_no_{profile.profile_id}",
                ):
                    _clear_idempotency(f"relink_{profile.profile_id}")
                    st.session_state.pop(confirm_key, None)
                    _rerun_ui()
        elif st.button(
            "Relink to this profile",
            key=f"speakers_relink_{profile.profile_id}",
        ):
            st.session_state[confirm_key] = True
            _rerun_ui()


@st.fragment
def _render_lifecycle(
    *,
    snap: AggregationSnapshot,
    profile: SpeakerProfileV1,
    directory_items: list[ProfileListItem],
    profile_blocked: bool,
) -> None:
    with st.expander("Lifecycle", expanded=False):
        sha = profile_content_sha256(profile.profile_id, root=snap.root)
        if not sha:
            st.error("Could not read profile content hash; lifecycle disabled.")
            return
        if profile_blocked:
            st.caption("Lifecycle actions disabled while this profile is blocked.")
            return

        svc = _service()
        c1, c2, c3 = st.columns(3)

        with c1:
            if profile.status == "active":
                if st.button(
                    "Archive profile",
                    key=f"speakers_archive_{profile.profile_id}",
                ):
                    payload = {
                        "profile_id": profile.profile_id,
                        "expected_content_sha256": sha,
                    }
                    try:
                        result = svc.archive_profile(
                            operation_idempotency_key=_idempotency_key(
                                f"archive_{profile.profile_id}", payload
                            ),
                            profile_id=profile.profile_id,
                            expected_content_sha256=sha,
                        )
                        consume_cache_invalidation_signal(result.cache_signal)
                        _clear_idempotency(f"archive_{profile.profile_id}")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            elif profile.status == "archived":
                if st.button(
                    "Unarchive profile",
                    key=f"speakers_unarchive_{profile.profile_id}",
                ):
                    payload = {
                        "profile_id": profile.profile_id,
                        "expected_content_sha256": sha,
                    }
                    try:
                        result = svc.unarchive_profile(
                            operation_idempotency_key=_idempotency_key(
                                f"unarchive_{profile.profile_id}", payload
                            ),
                            profile_id=profile.profile_id,
                            expected_content_sha256=sha,
                        )
                        consume_cache_invalidation_signal(result.cache_signal)
                        _clear_idempotency(f"unarchive_{profile.profile_id}")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

        with c2:
            active_others = sorted(
                (
                    i
                    for i in directory_items
                    if i.status == "active" and i.profile_id != profile.profile_id
                ),
                key=_surname_sort_key,
            )
            if profile.status == "active" and active_others:
                target = st.selectbox(
                    "Merge into",
                    options=[i.profile_id for i in active_others],
                    format_func=lambda pid: next(
                        (i.display_name for i in active_others if i.profile_id == pid), pid
                    ),
                    key=f"speakers_merge_target_{profile.profile_id}",
                )
                confirm_merge = f"speakers_confirm_merge_{profile.profile_id}"
                if st.session_state.get(confirm_merge):
                    st.caption(f"Merge into `{target}`?")
                    m1, m2 = st.columns(2)
                    with m1:
                        if st.button(
                            "Confirm merge",
                            key=f"speakers_merge_yes_{profile.profile_id}",
                            type="primary",
                        ):
                            payload = {
                                "source_profile_id": profile.profile_id,
                                "target_profile_id": target,
                                "expected_source_sha256": sha,
                            }
                            try:
                                result = svc.merge_profiles(
                                    operation_idempotency_key=_idempotency_key(
                                        f"merge_{profile.profile_id}", payload
                                    ),
                                    source_profile_id=profile.profile_id,
                                    target_profile_id=target,
                                    expected_source_sha256=sha,
                                )
                                consume_cache_invalidation_signal(result.cache_signal)
                                _clear_idempotency(f"merge_{profile.profile_id}")
                                st.session_state.pop(confirm_merge, None)
                                st.session_state[_SELECTED_KEY] = target
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
                    with m2:
                        if st.button(
                            "Cancel",
                            key=f"speakers_merge_no_{profile.profile_id}",
                        ):
                            _clear_idempotency(f"merge_{profile.profile_id}")
                            st.session_state.pop(confirm_merge, None)
                            _rerun_ui()
                elif st.button(
                    "Merge into selected",
                    key=f"speakers_merge_{profile.profile_id}",
                ):
                    st.session_state[confirm_merge] = True
                    _rerun_ui()

        with c3:
            st.caption(f"profile_id `{profile.profile_id}`")
