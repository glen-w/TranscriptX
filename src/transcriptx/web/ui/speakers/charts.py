"""Speakers profile charts, locations, interactions, and sentiment."""

from __future__ import annotations

from typing import Any

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
)
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.snapshot import (
    AggregationSnapshot,
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
from transcriptx.utils.html_utils import wrap_tooltip_text
from transcriptx.web.navigation import (
    navigate_highlight_to_transcript,
)


from transcriptx.web.ui.speakers.support import (
    _METHODOLOGY_CAPTIONS,
    _evidence_caption,
    _info_tooltip_html,
    _methodology_info_html,
    _methodology_lines,
)


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

    from transcriptx.core.maps_folium import create_location_map

    fmap = create_location_map(folium, zoom_start=2)
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
            st.iframe(map_html, height=400)
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
            icon=ic.ARTICLE,
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


def _series_points_frame(
    points: tuple[Any, ...], value_key: str
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in points:
        if p.value is None:
            continue
        rows.append({"period": p.display_label, value_key: float(p.value)})
    return rows
