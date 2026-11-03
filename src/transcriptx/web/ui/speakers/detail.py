"""Selected speaker profile header, voice, and section wiring."""

from __future__ import annotations


import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
    ProfileAggregate,
    ProfileListItem,
)
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.snapshot import (
    AggregationSnapshot,
)
from transcriptx.web.components.info_tooltip import widget_help
from transcriptx.web.speaker_avatar import speaker_heading_with_avatar_html


from transcriptx.web.ui.speakers.support import (
    _clear_idempotency,
    _idempotency_key,
    _service,
)

from transcriptx.web.ui.speakers.charts import (
    _render_detail_charts,
    _render_interactions_equity,
    _render_locations_map,
    _render_sentiment_trends,
)
from transcriptx.web.ui.speakers.forms import (
    _render_appearances_table,
    _render_edit_form,
    _render_lifecycle,
    _render_link_another,
)


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
        st.error(
            "Intersecting incomplete operations block some reads for this profile."
        )
    if profile_blocked:
        st.error(
            "Mutations are disabled while this profile intersects a blocking operation."
        )

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
        help=widget_help(
            f"Total words spoken across eligible appearances. {eligibility_help}"
        ),
    )
    m2.metric(
        "Turns",
        f"{agg.headline_turns:,}",
        help=widget_help(
            f"Total speaking turns across eligible appearances. {eligibility_help}"
        ),
    )
    m3.metric(
        "Duration (h)",
        f"{agg.headline_duration_seconds / 3600:,.1f}",
        help=widget_help(
            (
                "Total speaking duration across eligible appearances, in hours. "
                f"{eligibility_help}"
            )
        ),
    )
    m4.metric(
        "Appearances",
        f"{agg.headline_appearance_count:,}",
        help=widget_help(
            (
                "Linked appearances included in the word, turn, and duration totals. "
                f"{eligibility_help} The header count includes all linked appearances."
            )
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

    detail_tabs = (
        "Overview",
        "Appearances",
        "Trends",
        "Identity",
        "Voice & lifecycle",
    )
    detail_key = f"speakers_detail_tab_{profile.profile_id}"
    if st.session_state.get(detail_key) not in detail_tabs:
        st.session_state[detail_key] = detail_tabs[0]
    detail_tab = st.segmented_control(
        "Profile section",
        options=list(detail_tabs),
        key=detail_key,
        label_visibility="collapsed",
    )
    if detail_tab not in detail_tabs:
        detail_tab = detail_tabs[0]

    if detail_tab == "Overview":
        if profile.notes:
            st.markdown(profile.notes)
        else:
            st.caption("No notes yet — add them on the Identity tab.")
        st.caption(
            "Voice suggestions across the library: Settings → Speakers → "
            "Enrol trusted voice for all profiles, then Pre-load voice suggestions. "
            "Confirm matches in Speaker Identification; scores never auto-name."
        )
    elif detail_tab == "Appearances":
        links_by_id = {
            link.link_id: link
            for link in snap.links_by_profile.get(profile.profile_id, ())
        }
        _render_appearances_table(
            snap=snap,
            profile=profile,
            appearances=appearances,
            links_by_id=links_by_id,
            profile_blocked=profile_blocked,
        )
    elif detail_tab == "Trends":
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
    elif detail_tab == "Identity":
        if not profile_blocked:
            _render_edit_form(profile, root=snap.root)
        else:
            st.caption("Identity edits disabled while this profile is blocked.")
    else:
        if not profile_blocked and profile.status == "active":
            _render_voice_controls(snap=snap, profile=profile)
        if not profile_blocked and profile.status == "active":
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
        from transcriptx.core.speaker_profiles.voice.promote import (
            VoicePromotionService,
        )
        from transcriptx.core.speaker_profiles.voice.wipe import VoiceWipeService
    except Exception:
        return

    status = ActivationBarrier(snap.root).status()
    with st.expander("Voice evidence", expanded=False):
        if not status.allowed:
            st.caption(
                status.detail
                or (
                    "Local voice matching is not active "
                    f"({status.block_reason or 'unavailable'})."
                )
            )
            return

        samples = list_samples_for_profile(profile.profile_id, root=snap.root)
        eligible = sum(1 for s in samples if s.eligibility_state == "eligible")
        ineligible = sum(1 for s in samples if s.eligibility_state != "eligible")
        from transcriptx.core.speaker_profiles.voice.operator import VoiceOperatorStore

        bootstrap_max_links = VoiceOperatorStore(snap.root).read().bootstrap_max_links
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
            icon=ic.VOICE,
            help=widget_help(
                (
                    "Explicit bootstrap: extracts and embeds voice from this profile's "
                    "confirmed links (up to the Settings → Speakers enrol link cap). "
                    "Privacy opt-in alone does not enrol anything."
                )
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
                icon=ic.CHECK_CIRCLE,
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
            icon=ic.DELETE,
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
