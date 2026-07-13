"""Curated Overview blocks for the Standard (default) layout."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.run_health_presentation import build_run_status_summary
from transcriptx.web.summary_precedence import (
    resolve_primary_summary,
    quiet_unavailable_message,
)


def _loader(ctx: BlockContext):
    return ctx.services.content_loader


def _render_summary_body(candidate) -> None:
    if candidate.markdown:
        st.markdown(candidate.markdown)
        return
    payload = candidate.payload or {}
    if payload.get(candidate.text_field):
        st.markdown(str(payload[candidate.text_field]))
        return
    if payload:
        st.json(payload)


def render_transcript_summary_hero(
    ctx: BlockContext, _placement: BlockPlacement
) -> None:
    result = resolve_primary_summary(
        _loader(ctx),
        run_root=ctx.run_root,
        run_results=ctx.run_results,
    )
    if result.primary is None:
        st.info(result.unavailable_message)
        failed = [c for c in result.others if c.outcome == "failed"]
        if failed:
            with st.expander("Technical details"):
                for c in failed:
                    st.caption(f"{c.module}: {c.outcome}")
        return
    st.subheader(result.primary.title)
    _render_summary_body(result.primary)


def render_other_summaries(ctx: BlockContext, _placement: BlockPlacement) -> None:
    """Collapsed alternatives that did not win primary summary precedence."""
    result = resolve_primary_summary(
        _loader(ctx),
        run_root=ctx.run_root,
        run_results=ctx.run_results,
    )
    alternatives = [c for c in result.others if c.available or c.markdown or c.payload]
    if not alternatives:
        return
    with st.expander("Other summaries", expanded=False):
        for cand in alternatives:
            st.markdown(f"**{cand.title}**")
            if cand.available:
                _render_summary_body(cand)
            else:
                st.caption(quiet_unavailable_message(cand.title, outcome=cand.outcome))


def render_at_a_glance(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("At a glance")
    artifacts = ctx.artifacts
    speakers = sorted(
        {a.speaker for a in artifacts if a.speaker},
        key=lambda s: str(s).casefold(),
    )
    modules = {a.module for a in artifacts if a.module}
    chart_count = sum(1 for a in artifacts if (a.kind or "").startswith("chart"))
    data_count = sum(1 for a in artifacts if (a.kind or "").startswith("data"))

    duration_label = "—"
    loader = _loader(ctx)
    if loader is not None:
        stats = loader.load_json(
            "stats", "_stats.json"
        ) or loader.load_first_module_json("stats")
        if isinstance(stats, dict):
            dur = stats.get("duration_seconds") or stats.get("duration")
            if isinstance(dur, (int, float)) and dur > 0:
                mins = int(dur) // 60
                secs = int(dur) % 60
                duration_label = f"{mins}m {secs:02d}s"

    status = build_run_status_summary(
        Path(ctx.run_root) if ctx.run_root else Path("."),
        health=ctx.health,
        run_results=ctx.run_results,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Duration", duration_label)
    with c2:
        st.metric("Speakers", str(len(speakers) or "—"))
    with c3:
        st.metric("Modules", str(len(modules)))
    with c4:
        st.metric("Charts", str(chart_count))
    with c5:
        st.metric("Data files", str(data_count))
    st.caption(f"Run status: {status.user_facing_label}")


def render_speaker_summary_cards(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Speakers")
    loader = _loader(ctx)
    if loader is None or ctx.run_root is None:
        st.info(quiet_unavailable_message("Per-speaker summaries"))
        return
    index_payload = loader.load_json(
        "llm_speaker_summary", "_llm_speaker_summary_index.json"
    )
    if not index_payload:
        st.info(quiet_unavailable_message("Per-speaker summaries"))
        return
    speakers = index_payload.get("speakers") or []
    if not speakers:
        st.info(quiet_unavailable_message("Per-speaker summaries"))
        return

    cols = st.columns(min(3, len(speakers)))
    for i, entry in enumerate(speakers[:6]):
        speaker = str(entry.get("speaker") or "")
        status = str(entry.get("status") or "")
        with cols[i % len(cols)]:
            st.markdown(f"**{speaker or 'Speaker'}**")
            if status != "success":
                st.caption("Unavailable")
                continue
            safe = str(speaker).replace(" ", "_").replace("/", "_")
            md = loader.load_text(
                "llm_speaker_summary", f"_{safe}_llm_speaker_summary.md"
            )
            payload = loader.load_json(
                "llm_speaker_summary", f"_{safe}_llm_speaker_summary.json"
            )
            text = md or (payload or {}).get("summary") or ""
            if text:
                preview = str(text).strip().split("\n")[0][:220]
                st.caption(preview + ("…" if len(str(text).strip()) > 220 else ""))
            else:
                st.caption("No summary text.")


def render_action_items_compact(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Action items")
    loader = _loader(ctx)
    if loader is None:
        st.info(quiet_unavailable_message("Action items"))
        return
    payload = loader.load_json("llm_action_items", "_llm_action_items.json")
    items = (payload or {}).get("items") if isinstance(payload, dict) else None
    if not items:
        md = loader.load_text("llm_action_items", "_llm_action_items.md")
        if md:
            st.markdown(md[:800] + ("…" if len(md) > 800 else ""))
            return
        st.info(quiet_unavailable_message("Action items"))
        return
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if text:
            owner = item.get("owner")
            suffix = f" — {owner}" if owner else ""
            st.write(f"- {text}{suffix}")
    if len(items) > 5:
        st.caption(f"+{len(items) - 5} more on Insights → Actions")


def render_highlights_compact(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Highlights")
    loader = _loader(ctx)
    if loader is None:
        st.info(quiet_unavailable_message("Highlights"))
        return
    highlights = loader.load_json("highlights", "_highlights.json")
    if not highlights:
        st.info(quiet_unavailable_message("Highlights"))
        return
    themes = highlights.get("themes") or highlights.get("top_themes") or []
    quotes = highlights.get("quotes") or highlights.get("items") or []
    shown = 0
    for theme in themes[:3]:
        if isinstance(theme, dict):
            label = theme.get("label") or theme.get("theme") or theme.get("name")
        else:
            label = theme
        if label:
            st.write(f"- {label}")
            shown += 1
    if shown == 0:
        for q in quotes[:3]:
            if isinstance(q, dict):
                text = q.get("quote") or q.get("text") or ""
            else:
                text = str(q)
            if text:
                st.write(f"- {str(text)[:160]}")
                shown += 1
    if shown == 0:
        st.info(quiet_unavailable_message("Highlights"))


def render_run_status_compact(ctx: BlockContext, _placement: BlockPlacement) -> None:
    if ctx.run_root is None:
        return
    summary = build_run_status_summary(
        Path(ctx.run_root),
        health=ctx.health,
        run_results=ctx.run_results,
    )
    st.caption(f"**Run status:** {summary.user_facing_label}")
    st.caption(
        f"Artifact health: {summary.artifact_health} · "
        f"Execution: {summary.execution_status}"
    )
    if summary.technical_details:
        with st.expander("Technical details", expanded=False):
            for detail in summary.technical_details[:20]:
                prefix = detail.module_id or detail.source
                code = f" [{detail.error_code}]" if detail.error_code else ""
                st.write(f"- {prefix}{code}: {detail.message}")
            if summary.failed_count or summary.skipped_count or summary.blocked_count:
                st.caption(
                    f"Failed: {summary.failed_count} · "
                    f"Skipped: {summary.skipped_count} · "
                    f"Blocked: {summary.blocked_count}"
                )
            if st.button("Open Diagnostics", key="run_status_open_diagnostics"):
                st.session_state["page"] = "Diagnostics"
                st.rerun()
