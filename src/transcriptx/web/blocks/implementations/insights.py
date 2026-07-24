"""Insights page blocks — adapted from page_modules/insights.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import streamlit as st

from transcriptx.core.analysis.highlights.post_process import (
    collect_highlight_quotes,
    stable_quote_id,
)
from transcriptx.core.pipeline.manifest_loader import load_run_results
from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes
from transcriptx.utils.text_utils import format_time_detailed, is_named_speaker
from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.group_content import (
    group_rollup_empty_hint,
    is_group_run,
    list_group_members,
    load_group_blob,
    load_group_content_rows,
    load_group_session_rows,
    load_group_speaker_rows,
    load_member_module_json,
    load_member_module_text,
    member_empty_hint,
    select_group_member,
)
from transcriptx.core.llm_feedback.models import FeedbackSurface
from transcriptx.web.blocks.llm_presentation import (
    cleaned_llm_output_text,
    llm_surface_badges,
    render_badge_row,
    render_badge_row_with_feedback,
    render_markdown_without_heading_or_provenance,
    resolve_artifact_rel_path,
    strip_commitments_section,
)
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.components.module_run_prompt import render_module_required_hint
from transcriptx.web.speaker_accent import (
    load_accent_resolve_context,
    speaker_inline_html,
)
from transcriptx.web.navigation import (
    navigate_highlight_to_transcript,
    navigate_to_data_artifact,
)


def _loader(ctx: BlockContext):
    return ctx.services.content_loader


def _module_failure_hint(run_root: Path, module_id: str) -> str | None:
    rr_path = run_root / "run_results.json"
    if not rr_path.exists():
        return None
    try:
        from transcriptx.core.analysis.llm_support.action_items_guidance import (
            format_module_failure_for_user,
        )

        run_results = load_run_results(rr_path)
        for row in project_canonical_outcomes(run_results):
            if row.module_id == module_id and row.status == "failed":
                return format_module_failure_for_user(
                    module_id=module_id,
                    error_message=row.reason,
                    error_code=row.error_code,
                )
    except Exception:
        return None
    return None


def _segment_index_from_refs(item: Dict[str, Any]) -> int | None:
    refs = item.get("segment_refs") or {}
    indexes = refs.get("segment_indexes") or []
    if indexes:
        try:
            return int(indexes[0])
        except (TypeError, ValueError):
            return None
    return None


def _render_open_in_transcript_button(
    *,
    session_slug: str | None,
    run_id: str | None,
    segment_index: int | None,
    start_time: float | None,
    quote: str | None,
    button_key: str,
) -> None:
    if not session_slug or not run_id or segment_index is None:
        return
    if st.button("Open in transcript", key=button_key):
        navigate_highlight_to_transcript(
            session_slug=session_slug,
            run_id=run_id,
            segment_index=segment_index,
            start_time=start_time,
            highlight_query=(quote or "")[:120] or None,
        )


def _render_view_raw_file_link(
    ctx: BlockContext,
    module: str,
    suffix: str,
    *,
    link_key: str,
    storage_root: str | None = None,
    prefer_group_root: bool = False,
) -> None:
    loader = _loader(ctx)
    if loader is None:
        return
    artifact = loader.find_artifact(
        module,
        kind="data_json",
        suffix=suffix,
        storage_root=storage_root,
        prefer_group_root=prefer_group_root,
    )
    if artifact is None:
        artifact = loader.find_artifact(
            module,
            kind="data_txt",
            suffix=suffix.replace(".json", ".md"),
            storage_root=storage_root,
            prefer_group_root=prefer_group_root,
        )
    if artifact is None:
        return
    if st.button("View raw file", key=link_key):
        navigate_to_data_artifact(artifact_id=artifact.id)


def _render_quiet_module_empty(
    *,
    label: str,
    run_root: Path | None,
    module: str,
    empty_hint: str,
    ctx: BlockContext,
    key: str,
) -> None:
    """User-facing empty/failed message with optional Technical details."""
    from transcriptx.web.run_health_presentation import module_outcome_state
    from transcriptx.web.summary_precedence import quiet_unavailable_message

    outcome = module_outcome_state(run_root, module) if run_root else "unknown"
    if outcome in {"failed", "skipped", "blocked"}:
        st.info(quiet_unavailable_message(label, outcome=outcome))
        hint = _module_failure_hint(run_root, module) if run_root else None
        if hint:
            # Guidance is the action; keep it visible, not buried.
            st.warning(hint)
        return
    render_module_required_hint(empty_hint, key=key, ctx=ctx)


def _render_insights_payload(insights: Dict[str, Any]) -> None:
    key_themes = insights.get("key_themes") or []
    recurring_ideas = insights.get("recurring_ideas") or []
    style_markers = insights.get("style_markers") or {}
    st.caption("Key themes (content)")
    if not key_themes:
        st.write("No key themes available.")
    for row in key_themes[:8]:
        phrase = str(row.get("phrase") or "").strip()
        total = float((row.get("score") or {}).get("total", 0.0))
        if phrase:
            st.write(f"- {phrase} ({total:.3f})")
    st.caption("Recurring ideas (content recurrence)")
    if recurring_ideas:
        for row in recurring_ideas[:8]:
            phrase = str(row.get("phrase") or "").strip()
            recurrence = float((row.get("score") or {}).get("recurrence", 0.0))
            if phrase:
                st.write(f"- {phrase} (recurrence {recurrence:.3f})")
    st.caption("How people spoke (style markers)")
    st.json(style_markers)


def _render_insight_rows_rollup(rows: list[Dict[str, Any]]) -> None:
    themes = [r for r in rows if r.get("kind") == "key_theme"]
    ideas = [r for r in rows if r.get("kind") == "recurring_idea"]
    moments = [r for r in rows if r.get("kind") == "notable_moment"]
    st.caption("Group rollup — key themes")
    if not themes:
        st.write("No key themes across sessions.")
    for row in themes[:12]:
        text = str(row.get("text") or "").strip()
        score = row.get("score")
        suffix = f" ({float(score):.3f})" if isinstance(score, (int, float)) else ""
        session = row.get("order_index")
        prefix = f"[s{int(session) + 1}] " if session is not None else ""
        if text:
            st.write(f"- {prefix}{text}{suffix}")
    st.caption("Group rollup — recurring ideas")
    if ideas:
        for row in ideas[:12]:
            text = str(row.get("text") or "").strip()
            if text:
                st.write(f"- {text}")
    if moments:
        st.caption("Group rollup — notable moments")
        for row in moments[:8]:
            text = str(row.get("text") or "").strip()
            if text:
                st.write(f"- {text[:200]}")


def render_insights_contract(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Content vs Style")
    loader = _loader(ctx)
    run_root = ctx.run_root
    if loader is None and run_root is None:
        render_module_required_hint(
            "Run the `insights` module to populate this view.",
            key="insights_no_loader",
            ctx=ctx,
        )
        return

    if run_root is not None and is_group_run(run_root):
        from transcriptx.web.blocks.group_content import load_group_row_bundle

        bundle = load_group_row_bundle(run_root, "insights", "insight_rows")
        rows = bundle["content_rows"]
        session_rows = bundle["session_rows"]
        if session_rows:
            st.caption("Group rollup — per-session insight counts")
            st.dataframe(session_rows, width="stretch", hide_index=True)
        if rows:
            _render_insight_rows_rollup(rows)
        elif not session_rows:
            st.info(group_rollup_empty_hint("insights", content_name="insight_rows"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key="insights_session_select")
        if member is None:
            st.caption(member_empty_hint("insights"))
            return
        insights = load_member_module_json(loader, member, "insights", "_insights.json")
        if not insights:
            st.info(member_empty_hint("insights"))
            return
        _render_insights_payload(insights)
        _render_view_raw_file_link(
            ctx,
            "insights",
            "_insights.json",
            link_key="insights_member_raw",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(
            "Run the `insights` module to populate this view.",
            key="insights_no_loader",
            ctx=ctx,
        )
        return
    insights = loader.load_json("insights", "_insights.json")
    if not insights:
        render_module_required_hint(
            "Run the `insights` module to populate this view.",
            key="insights_empty",
            ctx=ctx,
        )
        return
    _render_insights_payload(insights)


def _highlights_theme_visible(theme: Dict[str, Any]) -> bool:
    has_q = bool(theme.get("quote_ids"))
    has_e = bool(theme.get("conflict_event_ids"))
    if theme.get("is_unthemed") and not has_q and not has_e:
        return False
    return has_q or has_e


def _render_highlights_theme_body(
    theme: Dict[str, Any],
    quotes_map: Dict[str, Dict[str, Any]],
    events_by_id: Dict[str, Dict[str, Any]],
    *,
    session_slug: str | None,
    run_id: str | None,
    key_prefix: str,
) -> None:
    accent_ctx = load_accent_resolve_context()
    for qid in theme.get("quote_ids") or []:
        item = quotes_map.get(qid)
        if not item:
            continue
        score = float((item.get("score") or {}).get("total") or 0.0)
        breakdown = (item.get("score") or {}).get("breakdown") or {}
        start = float(item.get("start") or 0.0)
        end = float(item.get("end") or 0.0)
        time_range = f"{format_time_detailed(start)}-{format_time_detailed(end)}"
        speaker = item.get("speaker") or ""
        speaker_html = speaker_inline_html(speaker, context=accent_ctx)
        if speaker_html:
            st.markdown(
                f"{speaker_html} · {time_range} · score {score:.3f}",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(f"{time_range} · score {score:.3f}")
        st.write(item.get("quote") or "")
        _render_open_in_transcript_button(
            session_slug=session_slug,
            run_id=run_id,
            segment_index=_segment_index_from_refs(item),
            start_time=start,
            quote=str(item.get("quote") or ""),
            button_key=f"{key_prefix}_theme_quote_{qid}",
        )
        with st.expander("Score breakdown"):
            st.json(breakdown)
    for eid in theme.get("conflict_event_ids") or []:
        ev = events_by_id.get(str(eid))
        if not ev:
            continue
        parts = [
            p.get("speaker_display")
            for p in ev.get("participants", []) or []
            if p.get("speaker_display")
        ]
        unique = list(dict.fromkeys(parts))
        part_text = ", ".join(unique) if unique else "speakers"
        st.caption(f"Tension ({part_text})")
        with st.expander("Event detail"):
            st.json(
                {
                    "event_id": ev.get("event_id"),
                    "start": ev.get("start"),
                    "end": ev.get("end"),
                    "score_breakdown": ev.get("score_breakdown"),
                }
            )


@st.fragment
def _highlights_browser_fragment(
    highlights: Dict[str, Any],
    *,
    session_slug: str | None,
    run_id: str | None,
) -> None:
    visible: list[Dict[str, Any]] = []
    themes = highlights.get("themes")
    if themes:
        visible = [t for t in themes if _highlights_theme_visible(t)]
        if visible:
            tk = str(highlights.get("transcript_key") or "unknown")
            quotes_map = {
                stable_quote_id(q, tk): q for q in collect_highlight_quotes(highlights)
            }
            conflict = highlights.get("sections", {}).get("conflict_points", {})
            events_by_id = {
                str(ev.get("event_id") or ""): ev
                for ev in conflict.get("events", []) or []
                if ev.get("event_id")
            }
            st.caption("Key themes and moments")
            if len(visible) <= 5:
                labels = [str(t.get("label") or "Theme") for t in visible]
                tabs = st.tabs(labels)
                for tab, theme in zip(tabs, visible):
                    with tab:
                        _render_highlights_theme_body(
                            theme,
                            quotes_map,
                            events_by_id,
                            session_slug=session_slug,
                            run_id=run_id,
                            key_prefix="hl_tab",
                        )
            else:
                choice = st.selectbox(
                    "Theme",
                    options=list(range(len(visible))),
                    format_func=lambda i: str(visible[i].get("label") or "Theme"),
                    key="highlights_theme_select",
                )
                theme = visible[int(choice)]
                _render_highlights_theme_body(
                    theme,
                    quotes_map,
                    events_by_id,
                    session_slug=session_slug,
                    run_id=run_id,
                    key_prefix="hl_sel",
                )
            st.divider()

    items = []
    sections = highlights.get("sections", {})
    for section_name, payload in sections.items():
        for item in (
            payload.get("items", [])
            if section_name == "cold_open"
            else payload.get("events", [])
        ):
            if section_name == "conflict_points":
                anchor = item.get("anchor_quote", {})
                items.append(
                    {
                        "section": "conflict_points",
                        "speaker": anchor.get("speaker", ""),
                        "start": anchor.get("start", 0.0),
                        "end": anchor.get("end", 0.0),
                        "quote": anchor.get("quote", ""),
                        "score": item.get("score_breakdown", {})
                        .get("window_spike_score", {})
                        .get("raw_window_score", 0.0),
                        "breakdown": item.get("score_breakdown", {}),
                    }
                )
            else:
                segment_index = _segment_index_from_refs(item)
                items.append(
                    {
                        "section": section_name,
                        "speaker": item.get("speaker", ""),
                        "start": item.get("start", 0.0),
                        "end": item.get("end", 0.0),
                        "quote": item.get("quote", ""),
                        "score": (item.get("score") or {}).get("total", 0.0),
                        "breakdown": (item.get("score") or {}).get("breakdown", {}),
                        "segment_index": segment_index,
                    }
                )

    if themes and visible:
        st.caption("All highlights (by section)")

    sections_available = sorted({item["section"] for item in items})
    speakers_available = sorted({item["speaker"] for item in items if item["speaker"]})
    section_filter = st.selectbox(
        "Section", options=["All"] + sections_available, key="highlights_section_filter"
    )
    speaker_filter = st.multiselect(
        "Speakers", options=speakers_available, key="highlights_speaker_filter"
    )
    min_score = st.slider(
        "Minimum score",
        min_value=0.0,
        max_value=1.0,
        value=0.0,
        step=0.05,
        key="highlights_min_score",
    )
    filtered = []
    for item in items:
        if section_filter != "All" and item["section"] != section_filter:
            continue
        if speaker_filter and item["speaker"] not in speaker_filter:
            continue
        if item["score"] < min_score:
            continue
        filtered.append(item)
    if not filtered:
        st.caption("No highlights match the current filters.")
        return
    accent_ctx = load_accent_resolve_context()
    for index, item in enumerate(filtered):
        time_range = (
            f"{format_time_detailed(item['start'])}-{format_time_detailed(item['end'])}"
        )
        st.markdown(
            (
                f"{speaker_inline_html(item['speaker'], context=accent_ctx)} · "
                f"{time_range} · score {item['score']:.3f}"
            ),
            unsafe_allow_html=True,
        )
        st.write(item["quote"])
        if item["section"] != "conflict_points":
            _render_open_in_transcript_button(
                session_slug=session_slug,
                run_id=run_id,
                segment_index=item.get("segment_index"),
                start_time=float(item.get("start") or 0.0),
                quote=str(item.get("quote") or ""),
                button_key=f"hl_row_{index}_{item['section']}",
            )
        with st.expander("Score breakdown"):
            st.json(item["breakdown"])


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
    st.subheader("Highlights")
    loader = _loader(ctx)
    run_root = ctx.run_root
    if loader is None and run_root is None:
        render_module_required_hint(
            "Run the `highlights` module to populate this view.",
            key="highlights_no_loader",
            ctx=ctx,
        )
        return

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
        )
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
    )


def _render_executive_summary_body(
    summary: Dict[str, Any] | None, md: str | None
) -> bool:
    if md:
        st.markdown(strip_commitments_section(md))
        return True
    if summary:
        display = (
            {k: v for k, v in summary.items() if k != "commitments"}
            if isinstance(summary, dict)
            else summary
        )
        st.json(display)
        return True
    return False


def _render_commitments_from_summary(summary: Dict[str, Any]) -> bool:
    commitments = (summary.get("commitments") or {}).get("items", [])
    if not commitments:
        return False
    st.subheader("Commitments / Next steps")
    rows = [
        {
            "owner": item.get("owner_display", ""),
            "action": item.get("action", ""),
            "start": item.get("timestamp", {}).get("start", 0.0),
            "end": item.get("timestamp", {}).get("end", 0.0),
        }
        for item in commitments
        if isinstance(item, dict)
    ]
    if not rows:
        return False
    st.dataframe(rows, width="stretch")
    return True


def render_executive_summary(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Executive Summary")
    loader = _loader(ctx)
    run_root = ctx.run_root
    if loader is None and run_root is None:
        render_module_required_hint(
            "Run the `summary` module to populate this view.",
            key="summary_no_loader",
            ctx=ctx,
        )
        return

    if run_root is not None and is_group_run(run_root):
        blob = load_group_blob(run_root, "summary", "summary")
        summaries = (blob or {}).get("summaries") if isinstance(blob, dict) else None
        if isinstance(summaries, list) and summaries:
            st.caption("Group rollup — collected session summaries")
            for entry in summaries:
                if not isinstance(entry, dict):
                    continue
                order = entry.get("order_index")
                label = f"Session {int(order) + 1}" if order is not None else "Session"
                with st.expander(label, expanded=len(summaries) == 1):
                    text = entry.get("summary") or entry.get("executive_summary")
                    if text:
                        st.markdown(str(text))
                    else:
                        display = {k: v for k, v in entry.items() if k != "commitments"}
                        st.json(display)
        else:
            st.info(group_rollup_empty_hint("summary", content_name="summary.json"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key="exec_summary_session_select")
        if member is None:
            return
        summary = load_member_module_json(loader, member, "summary", "_summary.json")
        md = load_member_module_text(loader, member, "summary", "_summary.md")
        if not _render_executive_summary_body(summary, md):
            st.info(member_empty_hint("summary"))
            return
        _render_view_raw_file_link(
            ctx,
            "summary",
            "_summary.json",
            link_key="exec_member_raw",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(
            "Run the `summary` module to populate this view.",
            key="summary_no_loader",
            ctx=ctx,
        )
        return
    summary = loader.load_json("summary", "_summary.json")
    md = loader.load_text("summary", "_summary.md")
    if not _render_executive_summary_body(summary, md):
        render_module_required_hint(
            "Run the `summary` module to populate this view.",
            key="summary_empty",
            ctx=ctx,
        )
        return
    _render_view_raw_file_link(
        ctx, "summary", "_summary.json", link_key="exec_view_raw"
    )


def render_commitments_table(ctx: BlockContext, _placement: BlockPlacement) -> None:
    loader = _loader(ctx)
    run_root = ctx.run_root
    if loader is None and run_root is None:
        return

    if run_root is not None and is_group_run(run_root):
        blob = load_group_blob(run_root, "summary", "summary")
        summaries = (blob or {}).get("summaries") if isinstance(blob, dict) else None
        collected: list[Dict[str, Any]] = []
        if isinstance(summaries, list):
            for entry in summaries:
                if not isinstance(entry, dict):
                    continue
                items = (entry.get("commitments") or {}).get("items") or []
                order = entry.get("order_index")
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    collected.append(
                        {
                            "session": (
                                f"s{int(order) + 1}" if order is not None else ""
                            ),
                            "owner": item.get("owner_display", ""),
                            "action": item.get("action", ""),
                            "start": item.get("timestamp", {}).get("start", 0.0),
                            "end": item.get("timestamp", {}).get("end", 0.0),
                        }
                    )
        if collected:
            st.subheader("Commitments / Next steps")
            st.caption("Group rollup")
            st.dataframe(collected, width="stretch")
        members = list_group_members(run_root)
        member = select_group_member(members, key="commitments_session_select")
        if member is None:
            return
        summary = load_member_module_json(loader, member, "summary", "_summary.json")
        if summary:
            st.caption(f"Per session — {member.label}")
            _render_commitments_from_summary(summary)
        return

    if loader is None:
        return
    summary = loader.load_json("summary", "_summary.json")
    if not summary:
        return
    _render_commitments_from_summary(summary)


def render_llm_summary_block(ctx: BlockContext, placement: BlockPlacement) -> None:
    module = str(placement.params.get("module", "llm_summary"))
    title = placement.title_override or str(
        placement.params.get("title", "LLM Transcript Summary")
    )
    artifact_stem = str(placement.params.get("artifact_stem", "_llm_summary"))
    text_field = str(placement.params.get("text_field", "summary"))
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            f"Run the `{module}` module (with LLM enabled) to populate this view.",
        )
    )
    instance_id = placement.params.get("instance_id")
    inst = str(instance_id) if instance_id else None

    st.subheader(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    if run_root is None:
        render_module_required_hint(empty_hint, key=f"llm_{module}_no_loader", ctx=ctx)
        return

    if is_group_run(run_root) and module in {"llm_summary", "narrative_summary"}:
        from transcriptx.web.summary_precedence import resolve_primary_summary

        result = resolve_primary_summary(
            loader, run_root=run_root, run_results=ctx.run_results
        )
        if result.primary and result.primary.available:
            st.caption("Group rollup — cross-session synthesis")
            if result.primary.markdown:
                st.markdown(result.primary.markdown)
            elif result.primary.payload and result.primary.payload.get(
                result.primary.text_field
            ):
                st.markdown(str(result.primary.payload[result.primary.text_field]))
            elif result.primary.payload:
                st.json(result.primary.payload)
        else:
            blob = load_group_blob(run_root, module, module)
            summaries = (
                (blob or {}).get("summaries") if isinstance(blob, dict) else None
            )
            if isinstance(summaries, list) and summaries:
                st.caption("Group rollup — collected member summaries")
                for entry in summaries:
                    if not isinstance(entry, dict):
                        continue
                    order = entry.get("order_index")
                    label = (
                        f"Session {int(order) + 1}" if order is not None else "Session"
                    )
                    with st.expander(label, expanded=False):
                        text = entry.get(text_field) or entry.get("summary")
                        if text:
                            st.markdown(str(text))
                        else:
                            st.json(entry)
            else:
                st.info(result.unavailable_message)
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key=f"llm_{module}_session_select")
        if member is None:
            return
        payload = load_member_module_json(
            loader, member, module, f"{artifact_stem}.json"
        )
        md = load_member_module_text(loader, member, module, f"{artifact_stem}.md")
        if md:
            st.markdown(md)
        elif payload and payload.get(text_field):
            st.markdown(str(payload[text_field]))
        elif payload:
            st.json(payload)
        else:
            st.info(member_empty_hint(module))
        return

    if loader is None:
        render_module_required_hint(empty_hint, key=f"llm_{module}_no_loader", ctx=ctx)
        return

    failure_hint = _module_failure_hint(run_root, module)
    payload = loader.load_json(module, f"{artifact_stem}.json", instance_id=inst)
    md = loader.load_text(module, f"{artifact_stem}.md", instance_id=inst)
    if not md and not (payload and (payload.get(text_field) or payload)):
        _render_quiet_module_empty(
            label=title,
            run_root=run_root,
            module=module,
            empty_hint=empty_hint if not failure_hint else empty_hint,
            ctx=ctx,
            key=f"llm_{module}_{inst or 'default'}",
        )
        return

    rated = (
        cleaned_llm_output_text(md)
        if md
        else str((payload or {}).get(text_field) or "")
    )
    rel = resolve_artifact_rel_path(
        loader, module, f"{artifact_stem}.md", instance_id=inst
    ) or resolve_artifact_rel_path(
        loader,
        module,
        f"{artifact_stem}.json",
        kind="data_json",
        instance_id=inst,
    )
    render_badge_row_with_feedback(
        llm_surface_badges((payload or {}).get("provenance") if payload else None),
        ctx=ctx,
        surface=FeedbackSurface.INSIGHTS_BLOCK,
        block_id=placement.block_id,
        module=module,
        artifact_rel_path=rel,
        output_text=rated,
        provenance=(payload or {}).get("provenance") if payload else None,
        placement_id=placement.placement_id,
        widget_key=f"fb_sum_{placement.placement_id}_{inst or 'default'}",
    )
    if md:
        st.markdown(md)
    elif payload and payload.get(text_field):
        st.markdown(str(payload[text_field]))
    elif payload:
        st.json(payload)
    suffix = f"{artifact_stem}.json"
    _render_view_raw_file_link(
        ctx, module, suffix, link_key=f"llm_raw_{module}_{inst or 'default'}"
    )
    prov = (payload or {}).get("provenance") or {}
    if not prov:
        return
    with st.expander("Generation details"):
        model = prov.get("model")
        provider = prov.get("provider")
        if model:
            st.write(f"Model: {model}")
        if provider:
            st.write(f"Provider: {provider}")
        if prov.get("truncated"):
            st.caption("Input was truncated to fit the model context window.")


def _safe_speaker_artifact_token(speaker: str) -> str:
    return str(speaker).replace(" ", "_").replace("/", "_")


def render_llm_speaker_summary_block(
    ctx: BlockContext, placement: BlockPlacement
) -> None:
    module = "llm_speaker_summary"
    title = placement.title_override or str(
        placement.params.get("title", "Per-Speaker LLM Summaries")
    )
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            "Run the `llm_speaker_summary` module (with LLM enabled and named "
            "speakers) to populate this view.",
        )
    )

    st.subheader(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    if run_root is None:
        render_module_required_hint(
            empty_hint, key="llm_speaker_summary_no_loader", ctx=ctx
        )
        return

    # Group runs: committed cross-session speaker index via central resolver.
    from transcriptx.core.analysis.group_llm_synthesis.resolve import (
        ResolverCache,
        load_group_speaker_index,
        load_group_speaker_summary,
        load_text_under_generation,
    )

    if is_group_run(run_root):
        cache = ResolverCache()
        index_payload = load_group_speaker_index(run_root, cache=cache)
        if index_payload:
            speakers = index_payload.get("speakers") or []
            st.caption("Cross-session Per-Speaker Summaries")
            for entry in speakers:
                if not isinstance(entry, dict):
                    continue
                speaker = str(
                    entry.get("display_name") or entry.get("canonical_speaker_id") or ""
                )
                status = str(entry.get("status") or "")
                if not speaker:
                    continue
                with st.expander(speaker, expanded=len(speakers) == 1):
                    if status != "success":
                        code = entry.get("error_code")
                        message = (
                            entry.get("error_message_safe") or "Summary unavailable"
                        )
                        detail = f"[{code}] {message}" if code else message
                        st.warning(detail)
                        continue
                    rel_json = str(entry.get("rel_json") or "")
                    rel_md = str(entry.get("rel_md") or "")
                    md = (
                        load_text_under_generation(run_root, rel_md, cache=cache)
                        if rel_md
                        else None
                    )
                    payload = (
                        load_group_speaker_summary(run_root, rel_json, cache=cache)
                        if rel_json
                        else None
                    )
                    render_badge_row(
                        llm_surface_badges(
                            (payload or {}).get("provenance") if payload else None
                        )
                    )
                    if md:
                        render_markdown_without_heading_or_provenance(md)
                    elif payload and payload.get("summary"):
                        st.markdown(str(payload["summary"]))
                    elif payload:
                        st.json(payload)
                    else:
                        st.caption("Artifact missing for this speaker.")
        else:
            st.info(
                "Cross-session per-speaker summaries unavailable. "
                "Browse a member session below if member artifacts exist."
            )
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key="llm_speaker_summary_session_select")
        if member is None:
            return
        index_payload = load_member_module_json(
            loader, member, module, "_llm_speaker_summary_index.json"
        )
        if not index_payload:
            st.info(member_empty_hint(module))
            return
        speakers = index_payload.get("speakers") or []
        for entry in speakers:
            speaker = str(entry.get("speaker", "") or "")
            status = str(entry.get("status", "") or "")
            if not speaker:
                continue
            safe = _safe_speaker_artifact_token(speaker)
            suffix_json = f"_{safe}_llm_speaker_summary.json"
            suffix_md = f"_{safe}_llm_speaker_summary.md"
            with st.expander(speaker, expanded=len(speakers) == 1):
                if status != "success":
                    code = entry.get("error_code")
                    message = entry.get("error_message") or "Summary generation failed"
                    detail = f"[{code}] {message}" if code else message
                    st.warning(detail)
                    continue
                md = load_member_module_text(loader, member, module, suffix_md)
                payload = load_member_module_json(loader, member, module, suffix_json)
                render_badge_row(
                    llm_surface_badges(
                        (payload or {}).get("provenance") if payload else None
                    )
                )
                if md:
                    render_markdown_without_heading_or_provenance(md)
                elif payload and payload.get("summary"):
                    st.markdown(str(payload["summary"]))
                elif payload:
                    st.json(payload)
                else:
                    st.caption("Artifact missing for this speaker.")
        return

    if loader is None:
        render_module_required_hint(
            empty_hint, key="llm_speaker_summary_no_loader", ctx=ctx
        )
        return

    index_payload = loader.load_json(module, "_llm_speaker_summary_index.json")
    if not index_payload:
        _render_quiet_module_empty(
            label="Per-speaker summaries",
            run_root=run_root,
            module=module,
            empty_hint=empty_hint,
            ctx=ctx,
            key="llm_speaker_summary_index",
        )
        from transcriptx.web.blocks.implementations.custom_qa_presentation import (
            render_speaker_custom_qa_fallback,
        )

        render_speaker_custom_qa_fallback(run_root)
        return

    speakers = index_payload.get("speakers") or []
    if not speakers:
        _render_quiet_module_empty(
            label="Per-speaker summaries",
            run_root=run_root,
            module=module,
            empty_hint=empty_hint,
            ctx=ctx,
            key="llm_speaker_summary_speakers",
        )
        from transcriptx.web.blocks.implementations.custom_qa_presentation import (
            render_speaker_custom_qa_fallback,
        )

        render_speaker_custom_qa_fallback(run_root)
        return

    for entry in speakers:
        speaker = str(entry.get("speaker", "") or "")
        status = str(entry.get("status", "") or "")
        if not speaker:
            continue
        safe = _safe_speaker_artifact_token(speaker)
        suffix_json = f"_{safe}_llm_speaker_summary.json"
        suffix_md = f"_{safe}_llm_speaker_summary.md"
        with st.expander(speaker, expanded=len(speakers) == 1):
            if status != "success":
                code = entry.get("error_code")
                message = entry.get("error_message") or "Summary generation failed"
                detail = f"[{code}] {message}" if code else message
                st.warning(detail)
                continue
            md = loader.load_text(module, suffix_md)
            payload = loader.load_json(module, suffix_json)
            rated = (
                cleaned_llm_output_text(md)
                if md
                else str((payload or {}).get("summary") or "")
            )
            rel = resolve_artifact_rel_path(
                loader, module, suffix_md
            ) or resolve_artifact_rel_path(
                loader, module, suffix_json, kind="data_json"
            )
            render_badge_row_with_feedback(
                llm_surface_badges(
                    (payload or {}).get("provenance") if payload else None
                ),
                ctx=ctx,
                surface=FeedbackSurface.INSIGHTS_BLOCK,
                block_id=placement.block_id,
                module=module,
                artifact_rel_path=rel,
                output_text=rated,
                provenance=(payload or {}).get("provenance") if payload else None,
                placement_id=placement.placement_id,
                widget_key=f"fb_spk_{placement.placement_id}_{safe}",
            )
            if md:
                render_markdown_without_heading_or_provenance(md)
            elif payload and payload.get("summary"):
                st.markdown(str(payload["summary"]))
            elif payload:
                st.json(payload)
            else:
                st.caption("Artifact missing for this speaker.")
                continue
            speaker_key = str(
                (payload or {}).get("speaker_key")
                or entry.get("speaker_key")
                or speaker
            )
            from transcriptx.web.blocks.implementations.custom_qa_presentation import (
                render_speaker_custom_qa,
            )

            render_speaker_custom_qa(
                run_root,
                speaker_key=speaker_key,
                key_prefix=f"spk_{safe}",
            )
            _render_view_raw_file_link(
                ctx,
                module,
                suffix_json,
                link_key=f"llm_speaker_raw_{safe}",
            )
            prov = (payload or {}).get("provenance") or {}
            if prov.get("truncated"):
                st.caption("Input was truncated to fit the model context window.")

    _render_view_raw_file_link(
        ctx,
        module,
        "_llm_speaker_summary_index.json",
        link_key="llm_speaker_index_raw",
    )


def _render_action_items_payload(
    payload: Dict[str, Any] | None, md: str | None
) -> bool:
    from transcriptx.core.analysis.llm_support.action_items_contract import (
        EMPTY_EXTRACTS_MESSAGE,
        HUMAN_REVIEW_BANNER,
        RECORD_TYPE_LABELS,
        is_v1_action_items_payload,
    )
    from transcriptx.core.analysis.llm_support.action_items_guidance import (
        empty_extracts_user_warning,
        truncated_output_user_warning,
    )

    if payload is not None and is_v1_action_items_payload(payload):
        st.caption(
            "Unstamped legacy action items (epoch-1 live path uses stamped schema)."
        )
        st.caption(HUMAN_REVIEW_BANNER)
    else:
        st.caption(HUMAN_REVIEW_BANNER)

    diagnostics = (
        (payload or {}).get("diagnostics") if isinstance(payload, dict) else None
    )
    trunc_warn = truncated_output_user_warning(diagnostics)
    if trunc_warn:
        st.warning(trunc_warn)
    empty_warn = empty_extracts_user_warning(diagnostics)
    if empty_warn:
        st.warning(empty_warn)

    if md:
        render_markdown_without_heading_or_provenance(md)
        return True
    if payload and isinstance(payload.get("items"), list):
        items = payload["items"]
        if not items:
            if not empty_warn:
                st.caption(EMPTY_EXTRACTS_MESSAGE)
            return True
        rows = [
            {
                "type": RECORD_TYPE_LABELS.get(
                    str(item.get("record_type") or "action_item"),
                    str(item.get("record_type") or "action_item"),
                ),
                "text": item.get("text", ""),
                "status": item.get("status", ""),
                "owner": item.get("owner") or "—",
                "deadline": item.get("deadline") or "—",
                "quote": item.get("quote") or "",
                "confidence": item.get("confidence"),
            }
            for item in items
            if isinstance(item, dict)
        ]
        st.dataframe(rows, width="stretch", hide_index=True)
        return True
    if payload:
        st.json(payload)
        return True
    return False


def _render_action_item_rows_rollup(rows: list[Dict[str, Any]]) -> None:
    from transcriptx.core.analysis.llm_support.action_items_contract import (
        HUMAN_REVIEW_BANNER,
        RECORD_TYPE_LABELS,
    )

    st.caption("Group rollup — meeting extracts across sessions")
    st.caption(HUMAN_REVIEW_BANNER)
    display = [
        {
            "session": (
                f"s{int(row['order_index']) + 1}"
                if row.get("order_index") is not None
                else ""
            ),
            "type": RECORD_TYPE_LABELS.get(
                str(row.get("record_type") or "action_item"),
                str(row.get("record_type") or "action_item"),
            ),
            "text": row.get("text") or "",
            "owner": row.get("owner") or "—",
            "deadline": row.get("deadline") or "—",
            "status": row.get("status") or "",
            "confidence": row.get("confidence"),
        }
        for row in rows
        if str(row.get("text") or "").strip()
    ]
    if not display:
        st.write("No meeting extracts.")
        return
    st.dataframe(display[:40], width="stretch", hide_index=True)
    if len(display) > 40:
        st.caption(f"+{len(display) - 40} more in Data")


def render_llm_action_items_block(ctx: BlockContext, placement: BlockPlacement) -> None:
    from transcriptx.core.analysis.llm_support.action_items_contract import (
        TITLE_MEETING_EXTRACTS,
    )

    module = "llm_action_items"
    title = placement.title_override or str(
        placement.params.get("title", TITLE_MEETING_EXTRACTS)
    )
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            "Run the `llm_action_items` module (with LLM enabled) to populate this view.",
        )
    )
    artifact_stem = str(placement.params.get("artifact_stem", "_llm_action_items"))

    st.subheader(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    if run_root is None:
        render_module_required_hint(
            empty_hint, key="llm_action_items_no_loader", ctx=ctx
        )
        return

    if is_group_run(run_root):
        rows = load_group_content_rows(run_root, module, "action_item_rows")
        if rows:
            _render_action_item_rows_rollup(rows)
        else:
            st.info(group_rollup_empty_hint(module, content_name="action_item_rows"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key="llm_action_items_session_select")
        if member is None:
            return
        payload = load_member_module_json(
            loader, member, module, f"{artifact_stem}.json"
        )
        md = load_member_module_text(loader, member, module, f"{artifact_stem}.md")
        render_badge_row(
            llm_surface_badges((payload or {}).get("provenance") if payload else None)
        )
        if not _render_action_items_payload(payload, md):
            st.info(member_empty_hint(module))
            return
        _render_view_raw_file_link(
            ctx,
            module,
            f"{artifact_stem}.json",
            link_key="llm_action_items_member_raw",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(
            empty_hint, key="llm_action_items_no_loader", ctx=ctx
        )
        return

    payload = loader.load_json(module, f"{artifact_stem}.json")
    md = loader.load_text(module, f"{artifact_stem}.md")
    rated = cleaned_llm_output_text(md) if md else ""
    if not rated and isinstance(payload, dict):
        items = payload.get("items") or []
        if isinstance(items, list):
            rated = "\n".join(
                str(it.get("text") or "")
                for it in items
                if isinstance(it, dict) and it.get("text")
            )
    rel = resolve_artifact_rel_path(
        loader, module, f"{artifact_stem}.md"
    ) or resolve_artifact_rel_path(
        loader, module, f"{artifact_stem}.json", kind="data_json"
    )
    render_badge_row_with_feedback(
        llm_surface_badges((payload or {}).get("provenance") if payload else None),
        ctx=ctx,
        surface=FeedbackSurface.INSIGHTS_BLOCK,
        block_id=placement.block_id,
        module=module,
        artifact_rel_path=rel,
        output_text=rated,
        provenance=(payload or {}).get("provenance") if payload else None,
        placement_id=placement.placement_id,
        widget_key=f"fb_ai_{placement.placement_id}",
    )
    if not _render_action_items_payload(payload, md):
        _render_quiet_module_empty(
            label=TITLE_MEETING_EXTRACTS,
            run_root=run_root,
            module=module,
            empty_hint=empty_hint,
            ctx=ctx,
            key="llm_action_items_empty",
        )
        return

    _render_view_raw_file_link(
        ctx, module, f"{artifact_stem}.json", link_key="llm_action_items_raw"
    )
    diagnostics = (payload or {}).get("diagnostics") or {}
    if diagnostics:
        with st.expander("Generation details"):
            st.json(diagnostics)


def _render_lexical_diversity_payload(payload: Dict[str, Any]) -> None:
    global_stats = payload.get("global_stats") or {}
    if isinstance(global_stats, dict) and global_stats:
        cols = st.columns(3)
        metrics = [
            ("TTR", global_stats.get("ttr")),
            ("MTLD", global_stats.get("mtld")),
            ("Hapax rate", global_stats.get("hapax_rate")),
        ]
        for col, (label, value) in zip(cols, metrics):
            if value is None:
                col.metric(label, "n/a")
            else:
                col.metric(label, f"{float(value):.3f}")

    speaker_stats = payload.get("speaker_stats") or {}
    if isinstance(speaker_stats, dict) and speaker_stats:
        rows = []
        for speaker in sorted(speaker_stats):
            if not is_named_speaker(str(speaker)):
                continue
            stats = speaker_stats[speaker]
            if not isinstance(stats, dict):
                continue
            rows.append(
                {
                    "speaker": speaker,
                    "token_count": stats.get("token_count"),
                    "type_count": stats.get("type_count"),
                    "ttr": stats.get("ttr"),
                    "mtld": stats.get("mtld"),
                    "hapax_rate": stats.get("hapax_rate"),
                }
            )
        if rows:
            st.caption(
                "Per-speaker metrics (TTR is length-sensitive; interpret in context)."
            )
            st.dataframe(rows, width="stretch", hide_index=True)

    time_buckets = payload.get("time_buckets") or []
    if isinstance(time_buckets, list) and time_buckets:
        bucket_rows = [
            {
                "bucket_start": bucket.get("bucket_start"),
                "bucket_end": bucket.get("bucket_end"),
                "ttr": bucket.get("ttr"),
                "mtld": bucket.get("mtld"),
                "token_count": bucket.get("token_count"),
            }
            for bucket in time_buckets
            if isinstance(bucket, dict)
        ]
        if bucket_rows:
            with st.expander("Time buckets"):
                st.dataframe(bucket_rows, width="stretch", hide_index=True)


def render_lexical_diversity_block(
    ctx: BlockContext, placement: BlockPlacement
) -> None:
    module = "lexical_diversity"
    title = placement.title_override or str(
        placement.params.get("title", "Lexical Diversity")
    )
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            "Run the `lexical_diversity` module to populate this view.",
        )
    )

    st.subheader(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    if run_root is None:
        render_module_required_hint(
            empty_hint, key="lexical_diversity_no_loader", ctx=ctx
        )
        return

    if is_group_run(run_root):
        session_rows = load_group_session_rows(run_root, module)
        speaker_rows = load_group_speaker_rows(run_root, module)
        if session_rows:
            st.caption("Group rollup — per-session metrics")
            st.dataframe(session_rows, width="stretch", hide_index=True)
        if speaker_rows:
            st.caption("Group rollup — per-speaker metrics")
            st.dataframe(speaker_rows[:40], width="stretch", hide_index=True)
        if not session_rows and not speaker_rows:
            st.info(group_rollup_empty_hint(module, content_name="session_rows"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key="lexical_diversity_session_select")
        if member is None:
            return
        payload = load_member_module_json(
            loader, member, module, "_lexical_diversity.json"
        )
        if not payload:
            st.info(member_empty_hint(module))
            return
        _render_lexical_diversity_payload(payload)
        _render_view_raw_file_link(
            ctx,
            module,
            "_lexical_diversity.json",
            link_key="lexical_diversity_member_raw",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(
            empty_hint, key="lexical_diversity_no_loader", ctx=ctx
        )
        return

    failure_hint = _module_failure_hint(run_root, module)
    payload = loader.load_json(module, "_lexical_diversity.json")
    if not payload:
        if failure_hint:
            st.warning(failure_hint)
        else:
            render_module_required_hint(
                empty_hint, key="lexical_diversity_empty", ctx=ctx
            )
        return

    _render_lexical_diversity_payload(payload)
    _render_view_raw_file_link(
        ctx, module, "_lexical_diversity.json", link_key="lexical_diversity_raw"
    )


def _render_marker_module_payload(
    payload: Dict[str, Any],
    *,
    share_keys: tuple[str, ...],
) -> None:
    if payload.get("usable") is False:
        meta = payload.get("metadata") or {}
        st.info(
            "Markers unavailable for this transcript "
            f"(language_status={meta.get('language_status', 'unsupported')})."
        )
        return

    global_stats = payload.get("global_stats") or {}
    if isinstance(global_stats, dict) and global_stats:
        cols = st.columns(min(3, 1 + len(share_keys)))
        cols[0].metric(
            "Hits / 100 tokens",
            (
                "n/a"
                if global_stats.get("hits_per_100_tokens") is None
                else f"{float(global_stats['hits_per_100_tokens']):.2f}"
            ),
        )
        for col, key in zip(cols[1:], share_keys):
            value = global_stats.get(key)
            label = key.replace("_", " ").title()
            if value is None:
                col.metric(label, "n/a")
            else:
                col.metric(label, f"{float(value):.3f}")

        counts = global_stats.get("category_counts") or {}
        if isinstance(counts, dict) and counts:
            st.caption("Global category counts")
            st.dataframe(
                [{"category": k, "count": v} for k, v in sorted(counts.items())],
                width="stretch",
                hide_index=True,
            )

    speaker_stats = payload.get("speaker_stats") or {}
    if isinstance(speaker_stats, dict) and speaker_stats:
        rows = []
        for speaker in sorted(speaker_stats):
            stats = speaker_stats[speaker]
            if not isinstance(stats, dict):
                continue
            row = {
                "speaker": speaker,
                "token_count": stats.get("token_count"),
                "total_marker_hits": stats.get("total_marker_hits"),
                "hits_per_100_tokens": stats.get("hits_per_100_tokens"),
            }
            for key in share_keys:
                row[key] = stats.get(key)
            rows.append(row)
        if rows:
            st.caption("Per-speaker marker rates")
            st.dataframe(rows, width="stretch", hide_index=True)

    hits = payload.get("hits") or []
    if isinstance(hits, list) and hits:
        with st.expander(f"Marker hits ({len(hits)})"):
            preview = [
                {
                    "speaker": h.get("speaker"),
                    "category": h.get("category"),
                    "surface": h.get("surface"),
                    "segment_index": h.get("segment_index"),
                }
                for h in hits[:80]
                if isinstance(h, dict)
            ]
            if preview:
                st.dataframe(preview, width="stretch", hide_index=True)


def _render_marker_module_block(
    ctx: BlockContext,
    placement: BlockPlacement,
    *,
    module: str,
    title_default: str,
    json_suffix: str,
    share_keys: tuple[str, ...],
) -> None:
    title = placement.title_override or str(
        placement.params.get("title", title_default)
    )
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            f"Run the `{module}` module to populate this view.",
        )
    )
    st.subheader(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    if run_root is None:
        render_module_required_hint(empty_hint, key=f"{module}_no_loader", ctx=ctx)
        return

    if is_group_run(run_root):
        session_rows = load_group_session_rows(run_root, module)
        speaker_rows = load_group_speaker_rows(run_root, module)
        if session_rows:
            st.caption("Group rollup — per-session metrics")
            st.dataframe(session_rows, width="stretch", hide_index=True)
        if speaker_rows:
            st.caption("Group rollup — per-speaker metrics")
            st.dataframe(speaker_rows[:40], width="stretch", hide_index=True)
        if not session_rows and not speaker_rows:
            st.info(group_rollup_empty_hint(module, content_name="session_rows"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session")
        member = select_group_member(members, key=f"{module}_session_select")
        if member is None:
            return
        payload = load_member_module_json(loader, member, module, json_suffix)
        if not payload:
            st.info(member_empty_hint(module))
            return
        _render_marker_module_payload(payload, share_keys=share_keys)
        _render_view_raw_file_link(
            ctx,
            module,
            json_suffix,
            link_key=f"{module}_member_raw",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(empty_hint, key=f"{module}_no_loader", ctx=ctx)
        return

    failure_hint = _module_failure_hint(run_root, module)
    payload = loader.load_json(module, json_suffix)
    if not payload:
        if failure_hint:
            st.warning(failure_hint)
        else:
            render_module_required_hint(empty_hint, key=f"{module}_empty", ctx=ctx)
        return

    _render_marker_module_payload(payload, share_keys=share_keys)
    _render_view_raw_file_link(ctx, module, json_suffix, link_key=f"{module}_raw")


def render_epistemic_markers_block(
    ctx: BlockContext, placement: BlockPlacement
) -> None:
    _render_marker_module_block(
        ctx,
        placement,
        module="epistemic_markers",
        title_default="Epistemic Markers",
        json_suffix="_epistemic_markers.json",
        share_keys=("hedge_share", "booster_share"),
    )


def render_politeness_block(ctx: BlockContext, placement: BlockPlacement) -> None:
    _render_marker_module_block(
        ctx,
        placement,
        module="politeness",
        title_default="Politeness Markers",
        json_suffix="_politeness.json",
        share_keys=("soft_request_ratio",),
    )


def _render_keyphrases_payload(payload: dict[str, Any]) -> None:
    usable = payload.get("usable")
    state = payload.get("evaluation_state")
    methods_run = payload.get("methods_run") or []
    skipped = payload.get("skipped_methods") or []
    if usable is False:
        reasons = []
        for item in skipped:
            if isinstance(item, dict):
                reasons.append(
                    f"{item.get('method')}: {item.get('reason_code')}"
                    + (f" ({item.get('detail')})" if item.get("detail") else "")
                )
        st.warning(
            "Keyphrases abstained"
            + (f" — evaluation_state={state}" if state else "")
            + (("; " + "; ".join(reasons)) if reasons else ".")
        )
        return
    if methods_run:
        st.caption("Methods run: " + ", ".join(str(m) for m in methods_run))
    if skipped:
        skip_bits = [
            f"{s.get('method')}:{s.get('reason_code')}"
            for s in skipped
            if isinstance(s, dict)
        ]
        if skip_bits:
            st.caption("Skipped methods: " + ", ".join(skip_bits))
    gbm = payload.get("global_by_method") or {}
    nc = gbm.get("noun_chunks") if isinstance(gbm, dict) else None
    phrases = (nc or {}).get("phrases") if isinstance(nc, dict) else None
    if not phrases:
        st.info("No noun-chunk keyphrases ranked for this transcript.")
        return
    rows = []
    for p in phrases[:40]:
        if not isinstance(p, dict):
            continue
        rows.append(
            {
                "rank": p.get("rank"),
                "phrase": p.get("phrase"),
                "rank_weight": p.get("rank_weight"),
                "occurrence_count": p.get("occurrence_count"),
                "segment_support": p.get("segment_support"),
                "token_count": p.get("token_count"),
            }
        )
    st.caption("Primary method: noun_chunks (method-separated; YAKE/KeyBERT not mixed)")
    st.dataframe(rows, width="stretch", hide_index=True)


def render_keyphrases_block(ctx: BlockContext, placement: BlockPlacement) -> None:
    title = placement.title_override or str(placement.params.get("title", "Keyphrases"))
    empty_hint = str(
        placement.params.get(
            "empty_hint",
            "Run the `keyphrases` module to populate this view.",
        )
    )
    st.subheader(title)
    loader = _loader(ctx)
    run_root = ctx.run_root
    module = "keyphrases"
    json_suffix = "_keyphrases.json"
    if run_root is None:
        render_module_required_hint(empty_hint, key=f"{module}_no_loader", ctx=ctx)
        return

    if is_group_run(run_root):
        session_rows = load_group_session_rows(run_root, module)
        if session_rows:
            st.caption("Group rollup — per-session noun_chunk counts")
            st.dataframe(session_rows, width="stretch", hide_index=True)
        else:
            st.info(group_rollup_empty_hint(module, content_name="session_rows"))
        members = list_group_members(run_root)
        st.divider()
        st.caption("Per session (noun_chunks primary)")
        member = select_group_member(members, key=f"{module}_session_select")
        if member is None:
            return
        payload = load_member_module_json(loader, member, module, json_suffix)
        if not payload:
            st.info(member_empty_hint(module))
            return
        _render_keyphrases_payload(payload)
        _render_view_raw_file_link(
            ctx,
            module,
            json_suffix,
            link_key=f"{module}_member_raw",
            storage_root=member.storage_root,
        )
        return

    if loader is None:
        render_module_required_hint(empty_hint, key=f"{module}_no_loader", ctx=ctx)
        return

    failure_hint = _module_failure_hint(run_root, module)
    payload = loader.load_json(module, json_suffix)
    if not payload:
        if failure_hint:
            st.warning(failure_hint)
        else:
            render_module_required_hint(empty_hint, key=f"{module}_empty", ctx=ctx)
        return

    _render_keyphrases_payload(payload)
    _render_view_raw_file_link(ctx, module, json_suffix, link_key=f"{module}_raw")
