"""Curated Overview blocks for the Standard (default) layout."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from transcriptx.utils.text_utils import format_duration_display_from_config
from transcriptx.core.analysis.llm_support.text_cleanup import (
    strip_llm_summary_preface,
)
from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.group_content import (
    is_group_run,
    load_group_content_rows,
    load_group_speaker_rows,
)
from transcriptx.web.blocks.llm_presentation import (
    provenance_badges,
    render_badge_row,
    render_markdown_without_heading_or_provenance,
    strip_commitments_section,
    strip_leading_markdown_heading,
    strip_provenance_footer,
)
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.components.module_run_prompt import render_module_required_hint
from transcriptx.web.speaker_accent import (
    SPEAKER_ACCENTS as _SPEAKER_ACCENTS,
    speaker_accent_color as _speaker_accent_color,
    speaker_heading_html,
)
from transcriptx.web.run_health_presentation import build_run_status_summary
from transcriptx.web.services.artifact_service import USER_REPORT_JSON
from transcriptx.web.summary_precedence import (
    SummaryKind,
    resolve_primary_summary,
    quiet_unavailable_message,
)


def _loader(ctx: BlockContext):
    return ctx.services.content_loader


def _summary_source_badge(kind: SummaryKind) -> str:
    if kind in {"llm_summary", "narrative_summary"}:
        return "LLM"
    return "Standard"


def _summary_hero_badges(candidate) -> list[str]:
    badges = [_summary_source_badge(candidate.kind)]
    badges.extend(provenance_badges((candidate.payload or {}).get("provenance")))
    return badges


def _render_summary_body(
    candidate, *, strip_heading: bool = False, strip_provenance: bool = False
) -> None:
    if candidate.markdown:
        body = candidate.markdown
        if candidate.kind == "executive_summary":
            body = strip_commitments_section(body)
        if strip_heading:
            body = strip_leading_markdown_heading(body)
        if strip_provenance:
            body = strip_provenance_footer(body)
        if candidate.kind in {"llm_summary", "narrative_summary"}:
            body = strip_llm_summary_preface(body)
        st.markdown(body)
        return
    payload = candidate.payload or {}
    if payload.get(candidate.text_field):
        text = str(payload[candidate.text_field])
        if candidate.kind in {"llm_summary", "narrative_summary"}:
            text = strip_llm_summary_preface(text)
        st.markdown(text)
        return
    if payload:
        # Keep commitments out of inline JSON dumps; Actions owns that table.
        if candidate.kind == "executive_summary" and "commitments" in payload:
            payload = {k: v for k, v in payload.items() if k != "commitments"}
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
        failed = [c for c in result.others if c.outcome == "failed"]
        if not failed and not result.others:
            render_module_required_hint(
                "Run the `summary` module to populate this view.",
                key="overview_summary_hero",
                ctx=ctx,
            )
            # Global custom QA fallback when summary hero is absent
            from transcriptx.web.blocks.implementations.custom_qa_presentation import (
                render_global_custom_qa_under_summary,
            )

            render_global_custom_qa_under_summary(ctx.run_root)
            return
        st.info(result.unavailable_message)
        if failed:
            with st.expander("Technical details"):
                for c in failed:
                    st.caption(f"{c.module}: {c.outcome}")
        from transcriptx.web.blocks.implementations.custom_qa_presentation import (
            render_global_custom_qa_under_summary,
        )

        render_global_custom_qa_under_summary(ctx.run_root)
        return
    st.markdown("# Transcript Summary")
    render_badge_row(_summary_hero_badges(result.primary))
    _render_summary_body(result.primary, strip_heading=True, strip_provenance=True)
    from transcriptx.web.blocks.implementations.custom_qa_presentation import (
        render_global_custom_qa_under_summary,
    )

    render_global_custom_qa_under_summary(ctx.run_root)


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


def _load_run_overview_payload(ctx: BlockContext) -> dict | None:
    """Prefer report.json overview; fall back to legacy stats artifacts."""
    if ctx.run_root is not None:
        report_path = Path(ctx.run_root) / USER_REPORT_JSON
        if report_path.is_file():
            try:
                payload = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict):
                return payload

    loader = _loader(ctx)
    if loader is None:
        return None
    for module, suffix in (
        ("report.json", "report.json"),
        ("stats", "_stats.json"),
    ):
        payload = loader.load_json(module, suffix)
        if isinstance(payload, dict):
            return payload
    payload = loader.load_first_module_json("stats")
    return payload if isinstance(payload, dict) else None


def _duration_seconds_from_overview(payload: dict | None) -> float | None:
    if not isinstance(payload, dict):
        return None
    overview = payload.get("overview")
    if isinstance(overview, dict):
        for key in ("total_duration_sec", "duration_seconds", "duration"):
            value = overview.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return float(value)
    for key in ("duration_seconds", "duration", "total_duration_sec"):
        value = payload.get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def _speaker_count_from_overview(payload: dict | None) -> int | None:
    if not isinstance(payload, dict):
        return None
    overview = payload.get("overview")
    if isinstance(overview, dict):
        for key in ("speaker_count_named", "speaker_count_total", "speaker_count"):
            value = overview.get(key)
            if isinstance(value, int) and value >= 0:
                return value
            if isinstance(value, float) and value >= 0:
                return int(value)
    speakers = payload.get("speakers")
    if isinstance(speakers, list) and speakers:
        return len(speakers)
    return None


def render_at_a_glance(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("At a glance")
    artifacts = ctx.artifacts
    modules = {a.module for a in artifacts if a.module}
    chart_count = sum(1 for a in artifacts if (a.kind or "").startswith("chart"))
    data_count = sum(1 for a in artifacts if (a.kind or "").startswith("data"))

    overview_payload = _load_run_overview_payload(ctx)
    duration_sec = _duration_seconds_from_overview(overview_payload)
    speaker_count = _speaker_count_from_overview(overview_payload)

    # Group runs: fall back to stats speaker_rows when report.json is absent.
    if (
        ctx.run_root is not None
        and is_group_run(ctx.run_root)
        and speaker_count is None
    ):
        speaker_rows = load_group_speaker_rows(Path(ctx.run_root), "stats")
        if speaker_rows:
            names = {
                str(r.get("canonical_speaker_id") or r.get("speaker") or "").strip()
                for r in speaker_rows
            }
            names.discard("")
            if names:
                speaker_count = len(names)

    duration_label = (
        format_duration_display_from_config(duration_sec)
        if duration_sec is not None
        else "—"
    )
    speakers_label = str(speaker_count) if speaker_count is not None else "—"

    status = build_run_status_summary(
        Path(ctx.run_root) if ctx.run_root else Path("."),
        health=ctx.health,
        run_results=ctx.run_results,
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Duration", duration_label)
    with c2:
        st.metric("Speakers", speakers_label)
    with c3:
        st.metric("Modules", str(len(modules)))
    with c4:
        st.metric("Charts", str(chart_count))
    with c5:
        st.metric("Data files", str(data_count))
    st.caption(f"Run status: {status.user_facing_label}")


def _format_pct(value: object) -> str:
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return "—"


def _format_wpm(value: object) -> str:
    try:
        return f"{float(value):.0f}"
    except (TypeError, ValueError):
        return "—"


def _speaker_fourth_stat(entry: dict) -> tuple[str, str]:
    """Pick one extra interesting metric for a speaker card."""
    tic = entry.get("tic_rate")
    try:
        if tic is not None and float(tic) >= 0.02:
            return "Tics", f"{float(tic):.0%}"
    except (TypeError, ValueError):
        pass

    sentiment = entry.get("sentiment")
    if isinstance(sentiment, dict):
        compound = sentiment.get("compound")
        try:
            if compound is not None and abs(float(compound)) >= 0.15:
                return "Tone", f"{float(compound):+.2f}"
        except (TypeError, ValueError):
            pass

    words_pct = entry.get("pct_total_words")
    if words_pct is not None:
        return "Words", _format_pct(words_pct)

    duration = str(entry.get("duration_hhmmss") or "").strip()
    if duration:
        return "Talk time", duration
    return "Words", "—"


def render_speaker_summary_cards(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Speakers")
    overview = _load_run_overview_payload(ctx)
    speakers = (overview or {}).get("speakers") if isinstance(overview, dict) else None

    # Group runs without report.json: synthesize cards from stats speaker_rows.
    if (
        (not isinstance(speakers, list) or not speakers)
        and ctx.run_root is not None
        and is_group_run(ctx.run_root)
    ):
        speaker_rows = load_group_speaker_rows(Path(ctx.run_root), "stats")
        speakers = []
        for row in speaker_rows:
            name = str(
                row.get("display_name")
                or row.get("canonical_speaker_id")
                or row.get("speaker")
                or ""
            ).strip()
            if not name:
                continue
            speakers.append(
                {
                    "name": name,
                    "pct_total_duration": row.get("pct_total_duration"),
                    "words_per_min": row.get("words_per_min"),
                    "segments": row.get("segment_count") or row.get("segments"),
                    "pct_total_words": row.get("pct_total_words"),
                    "duration_hhmmss": row.get("duration_hhmmss"),
                }
            )

    if not isinstance(speakers, list) or not speakers:
        st.info(quiet_unavailable_message("Per-speaker stats"))
        return

    ranked = sorted(
        [s for s in speakers if isinstance(s, dict)],
        key=lambda s: float(s.get("pct_total_duration") or 0),
        reverse=True,
    )
    if not ranked:
        st.info(quiet_unavailable_message("Per-speaker stats"))
        return

    cols = st.columns(min(3, len(ranked)))
    for i, entry in enumerate(ranked[:6]):
        name = str(entry.get("name") or "Speaker")
        # Prefer name-stable accents so the same speaker matches elsewhere
        # in the viewer; fall back to rank index only for empty names.
        accent = _speaker_accent_color(name if name.strip() else i)
        fourth_label, fourth_value = _speaker_fourth_stat(entry)
        with cols[i % len(cols)]:
            with st.container(border=True):
                st.markdown(
                    speaker_heading_html(
                        name, accent=accent, css_class="tx-speaker-card-title"
                    ),
                    unsafe_allow_html=True,
                )
                m1, m2 = st.columns(2)
                m1.metric("Time", _format_pct(entry.get("pct_total_duration")))
                m2.metric("WPM", _format_wpm(entry.get("words_per_min")))
                m3, m4 = st.columns(2)
                try:
                    segments = int(entry.get("segments") or 0)
                except (TypeError, ValueError):
                    segments = 0
                m3.metric("Segments", str(segments) if segments else "—")
                m4.metric(fourth_label, fourth_value)
    if len(ranked) > 6:
        st.caption(f"+{len(ranked) - 6} more speakers in the report")


def render_action_items_compact(ctx: BlockContext, _placement: BlockPlacement) -> None:
    from transcriptx.core.analysis.llm_support.action_items_contract import (
        HUMAN_REVIEW_BANNER,
        RECORD_TYPE_LABELS,
        TITLE_MEETING_EXTRACTS,
    )
    from transcriptx.core.analysis.llm_support.action_items_guidance import (
        empty_extracts_user_warning,
        format_module_failure_for_user,
        truncated_output_user_warning,
    )
    from transcriptx.web.run_health_presentation import module_outcome_state

    st.subheader(TITLE_MEETING_EXTRACTS)
    st.caption(HUMAN_REVIEW_BANNER)
    loader = _loader(ctx)
    run_root = ctx.run_root
    if loader is None and run_root is None:
        st.info(quiet_unavailable_message(TITLE_MEETING_EXTRACTS))
        return

    if run_root is not None and is_group_run(run_root):
        rows = load_group_content_rows(run_root, "llm_action_items", "action_item_rows")
        shown = 0
        for row in rows[:5]:
            text = str(row.get("text") or "").strip()
            if not text:
                continue
            owner = row.get("owner")
            record_type = str(row.get("record_type") or "action_item")
            type_label = RECORD_TYPE_LABELS.get(record_type, record_type)
            suffix = f" — {owner}" if owner else ""
            st.write(f"- [{type_label}] {text}{suffix}")
            shown += 1
        if shown:
            if len(rows) > 5:
                st.caption(f"+{len(rows) - 5} more on Insights → Meeting extracts")
            return
        st.info(quiet_unavailable_message(TITLE_MEETING_EXTRACTS))
        st.caption(
            "Browse per-session extracts on Insights → Meeting extracts when available."
        )
        return

    if loader is None:
        st.info(quiet_unavailable_message(TITLE_MEETING_EXTRACTS))
        return
    payload = loader.load_json("llm_action_items", "_llm_action_items.json")
    md = loader.load_text("llm_action_items", "_llm_action_items.md")
    render_badge_row(
        provenance_badges((payload or {}).get("provenance") if payload else None)
    )
    diagnostics = (
        (payload or {}).get("diagnostics") if isinstance(payload, dict) else None
    )
    trunc_warn = truncated_output_user_warning(diagnostics)
    if trunc_warn:
        st.warning(trunc_warn)
    empty_warn = empty_extracts_user_warning(diagnostics)
    if empty_warn:
        st.warning(empty_warn)
    items = (payload or {}).get("items") if isinstance(payload, dict) else None
    if items:
        for item in items[:5]:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if text:
                owner = item.get("owner")
                record_type = str(item.get("record_type") or "action_item")
                type_label = RECORD_TYPE_LABELS.get(record_type, record_type)
                suffix = f" — {owner}" if owner else ""
                st.write(f"- [{type_label}] {text}{suffix}")
        if len(items) > 5:
            st.caption(f"+{len(items) - 5} more on Insights → Meeting extracts")
        return
    if empty_warn:
        return
    if md:
        render_markdown_without_heading_or_provenance(md)
        return

    outcome = module_outcome_state(run_root, "llm_action_items", run_results=ctx.run_results)
    if outcome == "failed" and run_root is not None:
        st.info(quiet_unavailable_message(TITLE_MEETING_EXTRACTS, outcome=outcome))
        # Prefer guidance from run_results via shared formatter.
        from transcriptx.core.pipeline.manifest_loader import load_run_results
        from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes

        try:
            rr = ctx.run_results
            if rr is None:
                rr = load_run_results(run_root / "run_results.json")
            for row in project_canonical_outcomes(rr or {}):
                if row.module_id == "llm_action_items" and row.status == "failed":
                    st.warning(
                        format_module_failure_for_user(
                            module_id="llm_action_items",
                            error_message=row.reason,
                            error_code=row.error_code,
                        )
                    )
                    return
        except Exception:
            pass
        st.warning(
            format_module_failure_for_user(
                module_id="llm_action_items",
                error_message=None,
                error_code=None,
            )
        )
        return
    st.info(quiet_unavailable_message(TITLE_MEETING_EXTRACTS))


def render_highlights_compact(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Highlights")
    loader = _loader(ctx)
    run_root = ctx.run_root
    if loader is None and run_root is None:
        st.info(quiet_unavailable_message("Highlights"))
        return

    if run_root is not None and is_group_run(run_root):
        rows = load_group_content_rows(run_root, "highlights", "highlight_rows")
        shown = 0
        for row in rows[:5]:
            text = str(row.get("text") or "").strip()
            if text:
                st.write(f"- {text[:160]}")
                shown += 1
        if shown:
            return
        st.info(quiet_unavailable_message("Highlights"))
        st.caption(
            "Browse per-session highlights on Insights → Highlights when available."
        )
        return

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
    for theme in themes:
        if not isinstance(theme, dict):
            label = str(theme).strip()
            if label and label.lower() != "unthemed":
                st.write(f"- {label}")
                shown += 1
                if shown >= 3:
                    break
            continue
        has_q = bool(theme.get("quote_ids"))
        has_e = bool(theme.get("conflict_event_ids"))
        # Synthetic empty Unthemed (and any theme with no content) is not user-facing.
        if theme.get("is_unthemed") and not has_q and not has_e:
            continue
        if not (has_q or has_e):
            continue
        label = theme.get("label") or theme.get("theme") or theme.get("name")
        if label:
            st.write(f"- {label}")
            shown += 1
            if shown >= 3:
                break
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
        st.info("No highlight themes for this run.")


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
