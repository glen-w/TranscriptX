"""Curated Overview blocks for the Standard (default) layout."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.utils.text_utils import (
    format_bytes_display,
    format_duration_display_from_config,
)
from transcriptx.core.analysis.llm_support.text_cleanup import (
    strip_llm_summary_preface,
)
from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.group_content import (
    is_group_run,
    load_group_content_rows,
    load_group_speaker_rows,
)
from transcriptx.core.llm_feedback.models import FeedbackSurface
from transcriptx.web.blocks.llm_presentation import (
    AI_OUTPUT_BADGE,
    cleaned_llm_output_text,
    llm_surface_badges,
    provenance_badges,
    render_badge_row,
    render_badge_row_with_feedback,
    render_markdown_without_heading_or_provenance,
    resolve_artifact_rel_path,
    strip_commitments_section,
    strip_leading_markdown_heading,
    strip_provenance_footer,
)
from transcriptx.web.blocks.placement import BlockPlacement
from transcriptx.web.components.module_run_prompt import render_module_required_hint
from transcriptx.web.speaker_accent import (
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
from transcriptx.web.components.info_tooltip import widget_help


def _loader(ctx: BlockContext):
    return ctx.services.content_loader


def _summary_source_badge(kind: SummaryKind) -> str:
    if kind in {"llm_summary", "narrative_summary"}:
        return AI_OUTPUT_BADGE
    return "Deterministic"


def _analysis_preset_badge(run_results: dict | None) -> str | None:
    """Named UI preset badge (Quick/Balanced/Thorough); omit Custom / unknown."""
    from transcriptx.core.analysis.selection import analysis_preset_badge_label

    if not isinstance(run_results, dict):
        return None
    return analysis_preset_badge_label(run_results.get("analysis_preset"))


def _summary_hero_badges(candidate, *, run_results: dict | None = None) -> list[str]:
    badges: list[str] = []
    preset = _analysis_preset_badge(run_results)
    if preset:
        badges.append(preset)
    badges.append(_summary_source_badge(candidate.kind))
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
    primary = result.primary
    rated = ""
    if primary.markdown:
        rated = cleaned_llm_output_text(primary.markdown)
    elif primary.payload and primary.payload.get(primary.text_field):
        rated = str(primary.payload[primary.text_field])
    loader = _loader(ctx)
    module = str(getattr(primary, "module", None) or primary.kind or "llm_summary")
    stem = {
        "llm_summary": "_llm_summary",
        "narrative_summary": "_narrative_summary",
    }.get(str(primary.kind), "_llm_summary")
    rel = None
    if loader is not None and primary.kind in {"llm_summary", "narrative_summary"}:
        rel = resolve_artifact_rel_path(
            loader, module, f"{stem}.md"
        ) or resolve_artifact_rel_path(loader, module, f"{stem}.json", kind="data_json")
    if primary.kind in {"llm_summary", "narrative_summary"} and rated and rel:
        render_badge_row_with_feedback(
            _summary_hero_badges(primary, run_results=ctx.run_results),
            ctx=ctx,
            surface=FeedbackSurface.OVERVIEW_HERO,
            block_id=(
                _placement.block_id
                if _placement.block_id
                else "transcript_summary_hero"
            ),
            module=module,
            artifact_rel_path=rel,
            output_text=rated,
            provenance=(
                (primary.payload or {}).get("provenance") if primary.payload else None
            ),
            placement_id=_placement.placement_id,
            widget_key=f"fb_hero_{_placement.placement_id}",
        )
    else:
        render_badge_row(_summary_hero_badges(primary, run_results=ctx.run_results))
    _render_summary_body(primary, strip_heading=True, strip_provenance=True)
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


def _insights_summary_candidates(ctx: BlockContext) -> list:
    """All available summary kinds for Insights type selector (stable order)."""
    from transcriptx.web.insights_presentation import SUMMARY_TYPE_LABELS
    from transcriptx.web.summary_precedence import SummaryCandidate

    result = resolve_primary_summary(
        _loader(ctx),
        run_root=ctx.run_root,
        run_results=ctx.run_results,
    )
    by_kind: dict[str, SummaryCandidate] = {}
    for cand in (result.primary, *result.others):
        if cand is None:
            continue
        if cand.available or cand.markdown or cand.payload:
            by_kind[cand.kind] = cand
    ordered: list[SummaryCandidate] = []
    for kind in SUMMARY_TYPE_LABELS:
        cand = by_kind.get(kind)
        if cand is not None and (cand.available or cand.markdown or cand.payload):
            ordered.append(cand)
    return ordered


def render_insights_summary_panel(ctx: BlockContext, placement: BlockPlacement) -> None:
    """Insights Summary: one selectable summary body (Full controls)."""
    from transcriptx.web.insights_presentation import (
        SUMMARY_TYPE_LABELS,
        compact_metadata_chips,
        is_insights_guided,
        truncate_for_preview,
    )

    candidates = _insights_summary_candidates(ctx)
    if not candidates:
        result = resolve_primary_summary(
            _loader(ctx),
            run_root=ctx.run_root,
            run_results=ctx.run_results,
        )
        if result.unavailable_message:
            st.info(result.unavailable_message)
        else:
            render_module_required_hint(
                "Run a summary module to populate this view.",
                key="insights_summary_panel_empty",
                ctx=ctx,
            )
        from transcriptx.web.blocks.implementations.custom_qa_presentation import (
            render_global_custom_qa_under_summary,
        )

        render_global_custom_qa_under_summary(ctx.run_root)
        return

    labels = [SUMMARY_TYPE_LABELS.get(c.kind, c.title) for c in candidates]
    by_label = {SUMMARY_TYPE_LABELS.get(c.kind, c.title): c for c in candidates}
    # Prefer Transcript Summary when present; else first available.
    default_label = labels[0]
    for preferred in (
        SUMMARY_TYPE_LABELS["llm_summary"],
        SUMMARY_TYPE_LABELS["narrative_summary"],
        SUMMARY_TYPE_LABELS["executive_summary"],
    ):
        if preferred in by_label:
            default_label = preferred
            break

    state_key = f"insights_summary_type_{placement.placement_id}"
    if state_key not in st.session_state or st.session_state[state_key] not in by_label:
        st.session_state[state_key] = default_label

    if len(labels) > 1:
        try:
            choice = st.segmented_control(
                "Summary type",
                options=labels,
                default=st.session_state[state_key],
                key=f"{state_key}_control",
                help=widget_help(
                    "Switch between available Overview summary variants for this run."
                ),
            )
        except Exception:
            choice = st.radio(
                "Summary type",
                labels,
                index=labels.index(st.session_state[state_key]),
                horizontal=True,
                key=f"{state_key}_radio",
                help=widget_help(
                    "Switch between available Overview summary variants for this run."
                ),
            )
        if choice in by_label:
            st.session_state[state_key] = choice
    else:
        choice = labels[0]
        st.session_state[state_key] = choice

    selected = by_label[st.session_state[state_key]]
    title = SUMMARY_TYPE_LABELS.get(selected.kind, selected.title)
    st.markdown(f"## {title}")

    guided = is_insights_guided()
    badge_labels = compact_metadata_chips(
        _summary_hero_badges(selected, run_results=ctx.run_results)
    )
    rated = ""
    if selected.markdown:
        rated = cleaned_llm_output_text(selected.markdown)
    elif selected.payload and selected.payload.get(selected.text_field):
        rated = str(selected.payload[selected.text_field])

    loader = _loader(ctx)
    module = str(getattr(selected, "module", None) or selected.kind or "llm_summary")
    stem = {
        "llm_summary": "_llm_summary",
        "narrative_summary": "_narrative_summary",
        "executive_summary": "_summary",
    }.get(str(selected.kind), "_llm_summary")
    rel = None
    if loader is not None:
        rel = resolve_artifact_rel_path(
            loader, module, f"{stem}.md"
        ) or resolve_artifact_rel_path(loader, module, f"{stem}.json", kind="data_json")

    if selected.kind in {"llm_summary", "narrative_summary"} and rated and rel:
        render_badge_row_with_feedback(
            badge_labels,
            ctx=ctx,
            surface=FeedbackSurface.INSIGHTS_BLOCK,
            block_id=placement.block_id or "insights_summary_panel",
            module=module,
            artifact_rel_path=rel,
            output_text=rated,
            provenance=(
                (selected.payload or {}).get("provenance") if selected.payload else None
            ),
            placement_id=placement.placement_id,
            widget_key=f"fb_insights_sum_{placement.placement_id}_{selected.kind}",
        )
    else:
        render_badge_row(badge_labels)

    # Build display body once (no duplicate headings / stacked summaries).
    body_md = ""
    if selected.markdown:
        body_md = selected.markdown
        if selected.kind == "executive_summary":
            body_md = strip_commitments_section(body_md)
        body_md = strip_leading_markdown_heading(body_md)
        body_md = strip_provenance_footer(body_md)
        if selected.kind in {"llm_summary", "narrative_summary"}:
            body_md = strip_llm_summary_preface(body_md)
    elif selected.payload and selected.payload.get(selected.text_field):
        body_md = str(selected.payload[selected.text_field])
        if selected.kind in {"llm_summary", "narrative_summary"}:
            body_md = strip_llm_summary_preface(body_md)

    expand_key = f"insights_summary_full_{placement.placement_id}_{selected.kind}"
    if body_md:
        if guided:
            preview, truncated = truncate_for_preview(body_md)
            show_full = st.session_state.get(expand_key, False)
            if truncated and not show_full:
                st.markdown(preview)
                if st.button(
                    "Read full summary", key=f"{expand_key}_btn", icon=ic.SHOW_MORE
                ):
                    st.session_state[expand_key] = True
                    st.rerun()
            else:
                st.markdown(body_md)
                if truncated and show_full:
                    if st.button(
                        "Show preview", key=f"{expand_key}_collapse", icon=ic.SHOW_LESS
                    ):
                        st.session_state[expand_key] = False
                        st.rerun()
        else:
            st.markdown(body_md)
    elif selected.payload and not guided:
        # Full controls only: structured JSON fallback (never in Guided).
        payload = selected.payload
        if selected.kind == "executive_summary" and "commitments" in payload:
            payload = {k: v for k, v in payload.items() if k != "commitments"}
        st.json(payload)
    elif selected.payload and guided:
        st.info("Summary text is unavailable; open Full controls for structured data.")

    # Generation details — collapsed; one raw-file control inside.
    prov = (selected.payload or {}).get("provenance") if selected.payload else None
    with st.expander("Generation details", expanded=False):
        if isinstance(prov, dict) and prov:
            model = prov.get("model")
            provider = prov.get("provider")
            prompt_version = prov.get("prompt_version")
            if model:
                st.caption(f"Model: {model}")
            if provider:
                st.caption(f"Provider: {provider}")
            if prompt_version:
                st.caption(f"Prompt version: {prompt_version}")
            if not guided:
                st.json(prov)
        else:
            st.caption("No generation provenance recorded for this summary.")
        if loader is not None:
            from transcriptx.web.navigation import navigate_to_data_artifact

            artifact = loader.find_artifact(
                module, kind="data_json", suffix=f"{stem}.json"
            )
            if artifact is None:
                artifact = loader.find_artifact(
                    module, kind="data_txt", suffix=f"{stem}.md"
                )
            if artifact is not None:
                if st.button(
                    "View raw file",
                    key=f"insights_sum_raw_{placement.placement_id}_{selected.kind}",
                    icon=ic.INVENTORY,
                ):
                    navigate_to_data_artifact(artifact_id=artifact.id)

    from transcriptx.web.blocks.implementations.custom_qa_presentation import (
        render_global_custom_qa_under_summary,
    )

    render_global_custom_qa_under_summary(ctx.run_root)


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
    disk_bytes = sum(int(a.bytes or 0) for a in artifacts)

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

    c1, c2, c3, c4, c5, c6 = st.columns(6)
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
    with c6:
        st.metric("Size on disk", format_bytes_display(disk_bytes))
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
    from transcriptx.web.speaker_accent import (
        load_accent_resolve_context,
        resolve_speaker_accent,
    )

    accent_ctx = load_accent_resolve_context()

    for i, entry in enumerate(ranked[:6]):
        name = str(entry.get("name") or "Speaker")
        resolve_name = name if name.strip() else i
        if accent_ctx is not None:
            accent = resolve_speaker_accent(resolve_name, context=accent_ctx)
        else:
            accent = _speaker_accent_color(resolve_name)
        fourth_label, fourth_value = _speaker_fourth_stat(entry)
        with cols[i % len(cols)]:
            with st.container(border=True):
                st.markdown(
                    speaker_heading_html(
                        name,
                        accent=accent,
                        css_class="tx-speaker-card-title",
                        context=accent_ctx,
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
        loader, "llm_action_items", "_llm_action_items.md"
    ) or resolve_artifact_rel_path(
        loader, "llm_action_items", "_llm_action_items.json", kind="data_json"
    )
    render_badge_row_with_feedback(
        llm_surface_badges((payload or {}).get("provenance") if payload else None),
        ctx=ctx,
        surface=FeedbackSurface.INSIGHTS_BLOCK,
        block_id=_placement.block_id or "action_items_compact",
        module="llm_action_items",
        artifact_rel_path=rel,
        output_text=rated,
        provenance=(payload or {}).get("provenance") if payload else None,
        placement_id=_placement.placement_id,
        widget_key=f"fb_ai_ov_{_placement.placement_id}",
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

    outcome = module_outcome_state(
        run_root, "llm_action_items", run_results=ctx.run_results
    )
    if outcome == "failed" and run_root is not None:
        st.info(quiet_unavailable_message(TITLE_MEETING_EXTRACTS, outcome=outcome))
        # Prefer guidance from run_results via shared formatter.
        from transcriptx.core.pipeline.manifest_loader import load_run_results
        from transcriptx.core.pipeline.run_outcome_truth import (
            project_canonical_outcomes,
        )

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
            if st.button(
                "Open Diagnostics", key="run_status_open_diagnostics", icon=ic.DIAGNOSTICS
            ):
                st.session_state["page"] = "Diagnostics"
                st.rerun()
