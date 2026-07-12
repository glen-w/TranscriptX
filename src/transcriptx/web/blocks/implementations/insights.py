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
from transcriptx.utils.text_utils import format_time_detailed
from transcriptx.web.blocks.context import BlockContext
from transcriptx.web.blocks.placement import BlockPlacement
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
        run_results = load_run_results(rr_path)
        for row in project_canonical_outcomes(run_results):
            if row.module_id == module_id and row.status == "failed":
                detail = row.reason or ""
                if row.error_code:
                    prefix = f"[{row.error_code}]"
                    detail = f"{prefix} {detail}".strip()
                return (
                    detail or f"[{row.error_code}]"
                    if row.error_code
                    else "Module failed"
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
    ctx: BlockContext, module: str, suffix: str, *, link_key: str
) -> None:
    loader = _loader(ctx)
    if loader is None:
        return
    artifact = loader.find_artifact(module, kind="data_json", suffix=suffix)
    if artifact is None:
        artifact = loader.find_artifact(
            module, kind="data_txt", suffix=suffix.replace(".json", ".md")
        )
    if artifact is None:
        return
    if st.button("View raw file", key=link_key):
        navigate_to_data_artifact(artifact_id=artifact.id)


def render_insights_contract(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Content vs Style")
    loader = _loader(ctx)
    if loader is None:
        st.info("Run the `insights` module to populate this view.")
        return
    insights = loader.load_json("insights", "_insights.json")
    if not insights:
        st.info("Run the `insights` module to populate this view.")
        return
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
        st.markdown(f"**{speaker}** · {time_range} · score {score:.3f}")
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
    for index, item in enumerate(filtered):
        time_range = (
            f"{format_time_detailed(item['start'])}-{format_time_detailed(item['end'])}"
        )
        st.markdown(f"**{item['speaker']}** · {time_range} · score {item['score']:.3f}")
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


def render_highlights(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Highlights")
    loader = _loader(ctx)
    if loader is None:
        st.info("Run the `highlights` module to populate this view.")
        return
    highlights = loader.load_json("highlights", "_highlights.json")
    if not highlights:
        st.info("Run the `highlights` module to populate this view.")
        return
    _highlights_browser_fragment(
        highlights,
        session_slug=ctx.subject_id,
        run_id=ctx.run_id,
    )


def render_executive_summary(ctx: BlockContext, _placement: BlockPlacement) -> None:
    st.subheader("Executive Summary")
    loader = _loader(ctx)
    if loader is None:
        st.info("Run the `summary` module to populate this view.")
        return
    summary = loader.load_json("summary", "_summary.json")
    md = loader.load_text("summary", "_summary.md")
    if md:
        st.markdown(md)
    elif summary:
        st.json(summary)
    else:
        st.info("Run the `summary` module to populate this view.")
        return
    _render_view_raw_file_link(
        ctx, "summary", "_summary.json", link_key="exec_view_raw"
    )


def render_commitments_table(ctx: BlockContext, _placement: BlockPlacement) -> None:
    loader = _loader(ctx)
    if loader is None:
        return
    summary = loader.load_json("summary", "_summary.json")
    if not summary:
        return
    commitments = summary.get("commitments", {}).get("items", [])
    if not commitments:
        return
    st.subheader("Commitments / Next steps")
    rows = [
        {
            "owner": item.get("owner_display", ""),
            "action": item.get("action", ""),
            "start": item.get("timestamp", {}).get("start", 0.0),
            "end": item.get("timestamp", {}).get("end", 0.0),
        }
        for item in commitments
    ]
    st.dataframe(rows, width="stretch")


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
    if loader is None or run_root is None:
        st.info(empty_hint)
        return
    failure_hint = _module_failure_hint(run_root, module)
    payload = loader.load_json(module, f"{artifact_stem}.json", instance_id=inst)
    md = loader.load_text(module, f"{artifact_stem}.md", instance_id=inst)
    if md:
        st.markdown(md)
    elif payload and payload.get(text_field):
        st.markdown(str(payload[text_field]))
    elif payload:
        st.json(payload)
    else:
        if failure_hint:
            st.warning(failure_hint)
        else:
            st.info(empty_hint)
        return
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
    if loader is None or run_root is None:
        st.info(empty_hint)
        return

    failure_hint = _module_failure_hint(run_root, module)
    index_payload = loader.load_json(module, "_llm_speaker_summary_index.json")
    if not index_payload:
        if failure_hint:
            st.warning(failure_hint)
        else:
            st.info(empty_hint)
        return

    speakers = index_payload.get("speakers") or []
    if not speakers:
        st.info(empty_hint)
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
            if md:
                st.markdown(md)
            elif payload and payload.get("summary"):
                st.markdown(str(payload["summary"]))
            elif payload:
                st.json(payload)
            else:
                st.caption("Artifact missing for this speaker.")
                continue
            _render_view_raw_file_link(
                ctx,
                module,
                suffix_json,
                link_key=f"llm_speaker_raw_{safe}",
            )
            prov = (payload or {}).get("provenance") or {}
            if prov.get("truncated"):
                st.caption("Input was truncated to fit the model context window.")

    prov = index_payload.get("provenance") or {}
    if prov:
        with st.expander("Generation details"):
            model = prov.get("model")
            provider = prov.get("provider")
            if model:
                st.write(f"Model: {model}")
            if provider:
                st.write(f"Provider: {provider}")
            success_count = prov.get("success_count")
            failure_count = prov.get("failure_count")
            if success_count is not None:
                st.write(f"Summaries generated: {success_count}")
            if failure_count:
                st.write(f"Failed speakers: {failure_count}")
    _render_view_raw_file_link(
        ctx,
        module,
        "_llm_speaker_summary_index.json",
        link_key="llm_speaker_index_raw",
    )
