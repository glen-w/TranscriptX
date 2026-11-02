"""Highlights browser and rollup Insights blocks."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.core.analysis.highlights.post_process import (
    collect_highlight_quotes,
    stable_quote_id,
)
from transcriptx.utils.text_utils import format_time_detailed
from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.group_content import (
    group_rollup_empty_hint,
    is_group_run,
    list_group_members,
    load_group_content_rows,
    load_member_module_json,
    member_empty_hint,
    select_group_member,
)
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.components.module_run_prompt import render_module_required_hint
from transcriptx.web.speaker_accent import (
    load_accent_resolve_context,
    speaker_inline_html,
)
from transcriptx.web.navigation import (
    navigate_highlight_to_transcript,
)
from transcriptx.web.components.info_tooltip import widget_help

from transcriptx.web.blocks.implementations.insights_support import (
    _loader,
    _render_open_in_transcript_button,
    _render_view_raw_file_link,
    _segment_index_from_refs,
)


def _highlights_theme_visible(theme: Dict[str, Any]) -> bool:
    has_q = bool(theme.get("quote_ids"))
    has_e = bool(theme.get("conflict_event_ids"))
    if theme.get("is_unthemed") and not has_q and not has_e:
        return False
    return has_q or has_e


def _section_display_label(section: str) -> str:
    mapping = {
        "cold_open": "Cold open",
        "conflict_points": "Tension",
        "notable_moments": "Notable moment",
        "peak_moments": "Peak moment",
    }
    return mapping.get(section, section.replace("_", " ").title())


def _collect_highlight_cards(
    highlights: Dict[str, Any],
) -> list:
    """Flatten themes + sections into dedupe-ready cards (load once)."""
    from transcriptx.web.insights_presentation import (
        HighlightCardModel,
        theme_label_for_user,
    )

    tk = str(highlights.get("transcript_key") or "unknown")
    quotes_map = {
        stable_quote_id(q, tk): q for q in collect_highlight_quotes(highlights)
    }
    quote_to_theme: dict[str, str] = {}
    event_to_theme: dict[str, str] = {}
    themes = highlights.get("themes") or []
    for theme in themes:
        if not isinstance(theme, dict) or not _highlights_theme_visible(theme):
            continue
        label = theme_label_for_user(
            theme.get("label"),
            is_unthemed=bool(theme.get("is_unthemed")),
        )
        for qid in theme.get("quote_ids") or []:
            quote_to_theme[str(qid)] = label
        for eid in theme.get("conflict_event_ids") or []:
            event_to_theme[str(eid)] = label

    cards: list[HighlightCardModel] = []
    seen_keys: set[str] = set()

    # Theme-linked quotes first (prefer themed labels)
    for qid, item in quotes_map.items():
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote") or "").strip()
        start = float(item.get("start") or 0.0)
        end = float(item.get("end") or start)
        score_obj = item.get("score") or {}
        score = (
            float(score_obj.get("total") or 0.0) if isinstance(score_obj, dict) else 0.0
        )
        key = f"quote:{qid}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        speaker = str(item.get("speaker") or "").strip()
        cards.append(
            HighlightCardModel(
                event_key=key,
                theme_label=quote_to_theme.get(
                    str(qid), _section_display_label("notable_moments")
                ),
                speakers=(speaker,) if speaker else (),
                start=start,
                end=end,
                quote=quote,
                section=str(item.get("section") or "quotes"),
                score=score,
                breakdown=(
                    score_obj.get("breakdown") if isinstance(score_obj, dict) else None
                ),
                segment_index=_segment_index_from_refs(item),
                raw_event=item,
            )
        )

    sections = highlights.get("sections") or {}
    for section_name, payload in sections.items():
        if not isinstance(payload, dict):
            continue
        entries = (
            payload.get("items", [])
            if section_name == "cold_open"
            else payload.get("events", [])
        )
        for index, item in enumerate(entries or []):
            if not isinstance(item, dict):
                continue
            if section_name == "conflict_points":
                eid = str(item.get("event_id") or f"conflict_{index}")
                key = f"conflict:{eid}"
                if key in seen_keys:
                    continue
                # Skip if already represented via theme quote linkage with same event
                if eid in event_to_theme and any(c.event_key == key for c in cards):
                    continue
                seen_keys.add(key)
                anchor = item.get("anchor_quote") or {}
                quote = str(anchor.get("quote") or "").strip()
                start = float(anchor.get("start") or item.get("start") or 0.0)
                end = float(anchor.get("end") or item.get("end") or start)
                parts = [
                    p.get("speaker_display")
                    for p in item.get("participants", []) or []
                    if isinstance(p, dict) and p.get("speaker_display")
                ]
                speakers = tuple(dict.fromkeys(str(p) for p in parts if p))
                if not speakers and anchor.get("speaker"):
                    speakers = (str(anchor.get("speaker")),)
                score = (
                    item.get("score_breakdown", {})
                    .get("window_spike_score", {})
                    .get("raw_window_score", 0.0)
                )
                try:
                    score_f = float(score or 0.0)
                except (TypeError, ValueError):
                    score_f = 0.0
                cards.append(
                    HighlightCardModel(
                        event_key=key,
                        theme_label=event_to_theme.get(
                            eid, _section_display_label("conflict_points")
                        ),
                        speakers=speakers,
                        start=start,
                        end=end,
                        quote=quote,
                        section=section_name,
                        score=score_f,
                        breakdown=item.get("score_breakdown") or {},
                        segment_index=(
                            _segment_index_from_refs(anchor)
                            if isinstance(anchor, dict)
                            else None
                        ),
                        raw_event=item,
                    )
                )
            else:
                # Avoid duplicating quotes already collected via collect_highlight_quotes
                seg = _segment_index_from_refs(item)
                start = float(item.get("start") or 0.0)
                end = float(item.get("end") or start)
                quote = str(item.get("quote") or "").strip()
                key = f"{section_name}:{seg}:{start:.2f}:{quote[:40]}"
                # Skip if an equivalent quote card already exists
                duplicate = False
                for existing in cards:
                    if abs(existing.start - start) < 0.05 and existing.quote == quote:
                        duplicate = True
                        break
                if duplicate or key in seen_keys:
                    continue
                seen_keys.add(key)
                score_obj = item.get("score") or {}
                score = (
                    float(score_obj.get("total") or 0.0)
                    if isinstance(score_obj, dict)
                    else 0.0
                )
                speaker = str(item.get("speaker") or "").strip()
                cards.append(
                    HighlightCardModel(
                        event_key=key,
                        theme_label=_section_display_label(section_name),
                        speakers=(speaker,) if speaker else (),
                        start=start,
                        end=end,
                        quote=quote,
                        section=section_name,
                        score=score,
                        breakdown=(
                            score_obj.get("breakdown")
                            if isinstance(score_obj, dict)
                            else None
                        ),
                        segment_index=seg,
                        raw_event=item,
                    )
                )
    return cards


def _render_highlight_card(
    card,
    *,
    session_slug: str | None,
    run_id: str | None,
    index: int,
    guided: bool,
    accent_ctx,
    audio_available: bool = False,
) -> None:
    from transcriptx.web.insights_presentation import is_insights_full

    time_range = f"{format_time_detailed(card.start)}–{format_time_detailed(card.end)}"
    speakers_html = []
    for sp in card.speakers:
        html = speaker_inline_html(sp, context=accent_ctx)
        if html:
            speakers_html.append(html)
        else:
            speakers_html.append(sp)
    speakers_bit = ", ".join(speakers_html) if speakers_html else "Speaker"
    strength = ""
    if not guided and card.score is not None:
        strength = f" · {card.score:.2f}"
    elif guided and card.score is not None and card.score >= 0.75:
        strength = " · Strong"
    elif guided and card.score is not None and card.score >= 0.45:
        strength = " · Notable"

    with st.container(border=True):
        st.markdown(f"**{card.theme_label}**")
        st.markdown(
            f"{speakers_bit} · {time_range}{strength}",
            unsafe_allow_html=True,
        )
        st.write(card.quote)
        actions = st.columns(2 if audio_available else 1)
        with actions[0]:
            _render_open_in_transcript_button(
                session_slug=session_slug,
                run_id=run_id,
                segment_index=card.segment_index,
                start_time=card.start,
                quote=card.quote,
                button_key=f"hl_jump_{index}_{card.event_key}",
            )
        if audio_available and len(actions) > 1:
            with actions[1]:
                # Reuse transcript jump — Transcript page owns playback.
                if (
                    session_slug
                    and run_id
                    and card.segment_index is not None
                    and st.button(
                        "Play", key=f"hl_play_{index}_{card.event_key}", icon=ic.PLAY
                    )
                ):
                    navigate_highlight_to_transcript(
                        session_slug=session_slug,
                        run_id=run_id,
                        segment_index=card.segment_index,
                        start_time=card.start,
                        highlight_query=(card.quote or "")[:120] or None,
                    )
        if is_insights_full():
            with st.expander("Diagnostics", expanded=False):
                st.caption(f"Event: {card.event_key}")
                st.caption(f"Section: {card.section}")
                if card.score is not None:
                    st.caption(f"Score: {card.score:.3f}")
                if card.breakdown:
                    st.json(card.breakdown)
                if card.raw_event is not None:
                    with st.expander("Raw event"):
                        st.json(card.raw_event)


@st.fragment
def _highlights_browser_fragment(
    highlights: Dict[str, Any],
    *,
    session_slug: str | None,
    run_id: str | None,
    audio_available: bool = False,
) -> None:
    from transcriptx.web.insights_presentation import (
        GUIDED_HIGHLIGHT_CARD_CAP,
        dedupe_overlapping_highlights,
        highlight_quote_eligible,
        is_insights_guided,
    )

    guided = is_insights_guided()
    cards = _collect_highlight_cards(highlights)
    if not cards:
        st.info("No highlights available for this run.")
        return

    sections_available = sorted({c.section for c in cards if c.section})
    speakers_available = sorted({sp for c in cards for sp in c.speakers if sp})

    # Filters — collapsed unless active
    section_filter = st.session_state.get("highlights_section_filter", "All")
    speaker_filter = st.session_state.get("highlights_speaker_filter") or []
    min_score = float(st.session_state.get("highlights_min_score", 0.0) or 0.0)
    filters_active = section_filter != "All" or bool(speaker_filter) or min_score > 0.0
    filter_summary_parts = []
    if section_filter != "All":
        filter_summary_parts.append(f"section={section_filter}")
    if speaker_filter:
        filter_summary_parts.append(f"speakers={len(speaker_filter)}")
    if min_score > 0.0:
        filter_summary_parts.append(f"min score≥{min_score:.2f}")
    filter_label = (
        f"Filter highlights ({', '.join(filter_summary_parts)})"
        if filters_active
        else "Filter highlights"
    )
    with st.expander(filter_label, expanded=filters_active):
        st.selectbox(
            "Section",
            options=["All"] + sections_available,
            key="highlights_section_filter",
            help=widget_help("Limit highlights to one Insights section bucket."),
        )
        st.multiselect(
            "Speakers",
            options=speakers_available,
            key="highlights_speaker_filter",
            help=widget_help("Show only highlights involving the selected speakers."),
        )
        st.slider(
            "Minimum score",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            key="highlights_min_score",
            help=widget_help("Hide highlights ranked below this score."),
        )

    section_filter = st.session_state.get("highlights_section_filter", "All")
    speaker_filter = st.session_state.get("highlights_speaker_filter") or []
    min_score = float(st.session_state.get("highlights_min_score", 0.0) or 0.0)

    filtered = []
    for card in cards:
        if section_filter != "All" and card.section != section_filter:
            continue
        if speaker_filter and not any(sp in speaker_filter for sp in card.speakers):
            continue
        if (card.score or 0.0) < min_score:
            continue
        filtered.append(card)

    if guided:
        eligible = [c for c in filtered if highlight_quote_eligible(c.quote)]
        # Full controls still sees ineligible via unfiltered path when mode flips;
        # Guided promotes only usable excerpts.
        eligible = dedupe_overlapping_highlights(eligible)
        page_size = GUIDED_HIGHLIGHT_CARD_CAP
        shown_count = int(
            st.session_state.get("highlights_guided_shown", page_size) or page_size
        )
        shown_count = max(page_size, shown_count)
        display = eligible[:shown_count]
        if not display:
            st.caption("No eligible highlights for Guided view.")
            if filtered and is_insights_guided():
                st.caption("Switch to Full controls to browse all events.")
            return
        accent_ctx = load_accent_resolve_context()
        for index, card in enumerate(display):
            _render_highlight_card(
                card,
                session_slug=session_slug,
                run_id=run_id,
                index=index,
                guided=True,
                accent_ctx=accent_ctx,
                audio_available=audio_available,
            )
        if len(eligible) > shown_count:
            if st.button(
                f"Show more ({len(eligible) - shown_count} remaining)",
                key="highlights_show_more",
                icon=ic.SHOW_MORE,
            ):
                st.session_state["highlights_guided_shown"] = shown_count + page_size
                st.rerun()
        return

    # Full controls — no eligibility cull (still dedupe overlaps); windowed.
    all_cards = dedupe_overlapping_highlights(filtered)
    if not all_cards:
        st.caption("No highlights match the current filters.")
        return
    page_size = max(GUIDED_HIGHLIGHT_CARD_CAP, 12)
    shown_count = int(
        st.session_state.get("highlights_full_shown", page_size) or page_size
    )
    shown_count = max(page_size, shown_count)
    display = all_cards[:shown_count]
    accent_ctx = load_accent_resolve_context()
    for index, card in enumerate(display):
        _render_highlight_card(
            card,
            session_slug=session_slug,
            run_id=run_id,
            index=index,
            guided=False,
            accent_ctx=accent_ctx,
            audio_available=audio_available,
        )
    if len(all_cards) > shown_count:
        if st.button(
            f"Show more ({len(all_cards) - shown_count} remaining)",
            key="highlights_full_show_more",
            icon=ic.SHOW_MORE,
        ):
            st.session_state["highlights_full_shown"] = shown_count + page_size
            st.rerun()


def _render_highlight_rows_rollup(rows: list[Dict[str, Any]]) -> None:
    st.caption("Group rollup — highlights across sessions")
    shown = 0
    for row in rows[:12]:
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        speaker = str(row.get("speaker") or "").strip()
        score = row.get("score")
        session = row.get("order_index")
        parts = []
        if session is not None:
            parts.append(f"s{int(session) + 1}")
        if speaker:
            parts.append(speaker)
        if isinstance(score, (int, float)):
            parts.append(f"{float(score):.3f}")
        meta = " · ".join(parts)
        st.markdown(f"**{meta}**" if meta else "**Highlight**")
        st.write(text[:240])
        shown += 1
    if shown == 0:
        st.write("No highlight rows.")


def render_highlights(ctx: BlockContext, _placement: BlockPlacement) -> None:
    from transcriptx.web.insights_presentation import is_insights_guided

    st.markdown("## Highlights")
    loader = _loader(ctx)
    run_root = ctx.run_root
    if loader is None and run_root is None:
        render_module_required_hint(
            "Run the `highlights` module to populate this view.",
            key="highlights_no_loader",
            ctx=ctx,
        )
        return

    audio_available = _highlights_audio_available(ctx)

    if run_root is not None and is_group_run(run_root):
        rows = load_group_content_rows(run_root, "highlights", "highlight_rows")
        if rows:
            _render_highlight_rows_rollup(rows)
        else:
            st.info(
                group_rollup_empty_hint("highlights", content_name="highlight_rows")
            )
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key="highlights_session_select")
        if member is None:
            st.caption(member_empty_hint("highlights"))
            return
        highlights = load_member_module_json(
            loader, member, "highlights", "_highlights.json"
        )
        if not highlights:
            st.info(member_empty_hint("highlights"))
            return
        _highlights_browser_fragment(
            highlights,
            session_slug=Path(member.transcript_path).stem or ctx.subject_id,
            run_id=member.run_id or ctx.run_id,
            audio_available=audio_available,
        )
        if is_insights_guided():
            with st.expander("Data and provenance", expanded=False):
                _render_view_raw_file_link(
                    ctx,
                    "highlights",
                    "_highlights.json",
                    link_key="highlights_member_raw",
                    storage_root=member.storage_root,
                )
        else:
            _render_view_raw_file_link(
                ctx,
                "highlights",
                "_highlights.json",
                link_key="highlights_member_raw",
                storage_root=member.storage_root,
            )
        return

    if loader is None:
        render_module_required_hint(
            "Run the `highlights` module to populate this view.",
            key="highlights_no_loader",
            ctx=ctx,
        )
        return
    highlights = loader.load_json("highlights", "_highlights.json")
    if not highlights:
        render_module_required_hint(
            "Run the `highlights` module to populate this view.",
            key="highlights_empty",
            ctx=ctx,
        )
        return
    _highlights_browser_fragment(
        highlights,
        session_slug=ctx.subject_id,
        run_id=ctx.run_id,
        audio_available=audio_available,
    )
    if is_insights_guided():
        with st.expander("Data and provenance", expanded=False):
            _render_view_raw_file_link(
                ctx, "highlights", "_highlights.json", link_key="highlights_raw"
            )
    else:
        _render_view_raw_file_link(
            ctx, "highlights", "_highlights.json", link_key="highlights_raw"
        )


def _highlights_audio_available(ctx: BlockContext) -> bool:
    """Cheap gate for Play — Transcript page still owns actual playback."""
    try:
        from transcriptx.web.components.playback_panel import (
            resolve_playback_availability,
        )
        from transcriptx.services.speaker_studio.controller import (
            SpeakerStudioController,
        )

        subject_id = getattr(ctx, "subject_id", None) or st.session_state.get(
            "subject_id"
        )
        # Prefer an explicit transcript path from session when present.
        path = st.session_state.get("transcript_path")
        if not path and subject_id:
            # Without a resolved path, avoid expensive discovery — hide Play.
            return False
        if not path:
            return False
        controller = SpeakerStudioController()
        availability = resolve_playback_availability(str(path), controller)
        return bool(availability.enabled)
    except Exception:
        return False
