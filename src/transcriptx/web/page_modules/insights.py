"""Highlights and Summary insights viewer.

Highlights filter widgets run in ``@st.fragment`` so filter changes do not trigger
a full-app rerun.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

from typing import cast

from transcriptx.core.analysis.highlights.post_process import (  # type: ignore[import-untyped]
    collect_highlight_quotes,
    stable_quote_id,
)
from transcriptx.web.services import ArtifactService, RunIndex, SubjectService  # type: ignore[import-untyped]
from transcriptx.utils.text_utils import (  # type: ignore[import-untyped]
    format_time_detailed,
)


def render_insights() -> None:
    subject = SubjectService.resolve_current_subject(st.session_state)
    run_id = st.session_state.get("run_id")
    if not subject or not run_id:
        st.info("Select a subject and run to view insights.")
        return
    run_root = RunIndex.get_run_root(
        subject.scope,
        run_id,
        subject_id=subject.subject_id,
    )

    st.markdown("## 🛈 Insights")
    _render_insights_contract_section(run_root)
    st.divider()
    _render_highlights_section(run_root)
    st.divider()
    _render_summary_section(run_root)
    st.divider()
    _render_llm_module_section(
        run_root,
        module="llm_summary",
        title="LLM Transcript Summary",
        artifact_stem="_llm_summary",
        text_field="summary",
        empty_hint="Run the `llm_summary` module (with LLM enabled) to populate this view.",
    )
    st.divider()
    _render_llm_module_section(
        run_root,
        module="narrative_summary",
        title="Narrative Summary",
        artifact_stem="_narrative_summary",
        text_field="narrative",
        empty_hint="Run the `narrative_summary` module (with LLM enabled) to populate this view.",
    )


def _render_insights_contract_section(run_root: Path) -> None:
    st.subheader("Content vs Style")
    insights = _load_artifact_json(run_root, "insights", "_insights.json")
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


def _load_artifact_json(
    run_root: Path, module: str, suffix: str
) -> Optional[Dict[str, Any]]:
    artifacts = ArtifactService.list_artifacts(run_root)
    match = next(
        (
            a
            for a in artifacts
            if a.module == module
            and a.kind == "data_json"
            and a.rel_path.endswith(suffix)
        ),
        None,
    )
    if not match:
        return None
    path = ArtifactService._resolve_safe_path(run_root, match.rel_path)
    if path is None or not path.exists():
        return None
    return cast(Dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _load_artifact_text(run_root: Path, module: str, suffix: str) -> Optional[str]:
    artifacts = ArtifactService.list_artifacts(run_root)
    match = next(
        (
            a
            for a in artifacts
            if a.module == module
            and a.kind == "data_txt"
            and a.rel_path.endswith(suffix)
        ),
        None,
    )
    if not match:
        return None
    path = ArtifactService._resolve_safe_path(run_root, match.rel_path)
    if path is None or not path.exists():
        return None
    return cast(str, path.read_text(encoding="utf-8", errors="ignore"))


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
def _highlights_browser_fragment(highlights: Dict[str, Any]) -> None:
    """Theme navigation and highlight filters without full-app rerun."""
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
                        _render_highlights_theme_body(theme, quotes_map, events_by_id)
            else:
                choice = st.selectbox(
                    "Theme",
                    options=list(range(len(visible))),
                    format_func=lambda i: str(visible[i].get("label") or "Theme"),
                    key="highlights_theme_select",
                )
                theme = visible[int(choice)]
                _render_highlights_theme_body(theme, quotes_map, events_by_id)
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
                items.append(
                    {
                        "section": section_name,
                        "speaker": item.get("speaker", ""),
                        "start": item.get("start", 0.0),
                        "end": item.get("end", 0.0),
                        "quote": item.get("quote", ""),
                        "score": (item.get("score") or {}).get("total", 0.0),
                        "breakdown": (item.get("score") or {}).get("breakdown", {}),
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

    for item in filtered:
        time_range = (
            f"{format_time_detailed(item['start'])}-{format_time_detailed(item['end'])}"
        )
        st.markdown(f"**{item['speaker']}** · {time_range} · score {item['score']:.3f}")
        st.write(item["quote"])
        with st.expander("Score breakdown"):
            st.json(item["breakdown"])


def _render_highlights_section(run_root: Path) -> None:
    st.subheader("Highlights")
    highlights = _load_artifact_json(run_root, "highlights", "_highlights.json")
    if not highlights:
        st.info("Run the `highlights` module to populate this view.")
        return

    _highlights_browser_fragment(highlights)


def _render_llm_module_section(
    run_root: Path,
    *,
    module: str,
    title: str,
    artifact_stem: str,
    text_field: str,
    empty_hint: str,
) -> None:
    st.subheader(title)
    payload = _load_artifact_json(run_root, module, f"{artifact_stem}.json")
    md = _load_artifact_text(run_root, module, f"{artifact_stem}.md")
    if md:
        st.markdown(md)
    elif payload and payload.get(text_field):
        st.markdown(str(payload[text_field]))
    elif payload:
        st.json(payload)
    else:
        st.info(empty_hint)
        return

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


def _render_summary_section(run_root: Path) -> None:
    st.subheader("Executive Summary")
    summary = _load_artifact_json(run_root, "summary", "_summary.json")
    md = _load_artifact_text(run_root, "summary", "_summary.md")
    if md:
        st.markdown(md)
    elif summary:
        st.json(summary)
    else:
        st.info("Run the `summary` module to populate this view.")
        return

    if not summary:
        return
    commitments = summary.get("commitments", {}).get("items", [])
    if commitments:
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
