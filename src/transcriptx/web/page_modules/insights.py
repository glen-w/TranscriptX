"""Highlights and Summary insights viewer."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st

from typing import cast

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
    _render_highlights_section(run_root)
    st.divider()
    _render_summary_section(run_root)


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


def _load_artifact_text(
    run_root: Path, module: str, suffix: str
) -> Optional[str]:
    artifacts = ArtifactService.list_artifacts(run_root)
    match = next(
        (
            a
            for a in artifacts
            if a.module == module and a.kind == "data_txt" and a.rel_path.endswith(suffix)
        ),
        None,
    )
    if not match:
        return None
    path = ArtifactService._resolve_safe_path(run_root, match.rel_path)
    if path is None or not path.exists():
        return None
    return cast(str, path.read_text(encoding="utf-8", errors="ignore"))


def _render_highlights_section(run_root: Path) -> None:
    st.subheader("Highlights")
    highlights = _load_artifact_json(run_root, "highlights", "_highlights.json")
    if not highlights:
        st.info("Run the `highlights` module to populate this view.")
        return

    items = []
    sections = highlights.get("sections", {})
    for section_name, payload in sections.items():
        for item in payload.get("items", []) if section_name == "cold_open" else payload.get("events", []):
            if section_name == "conflict_points":
                anchor = item.get("anchor_quote", {})
                items.append(
                    {
                        "section": "conflict_points",
                        "speaker": anchor.get("speaker", ""),
                        "start": anchor.get("start", 0.0),
                        "end": anchor.get("end", 0.0),
                        "quote": anchor.get("quote", ""),
                        "score": item.get("score_breakdown", {}).get("window_spike_score", {}).get("raw_window_score", 0.0),
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
                        "score": item.get("score", {}).get("total", 0.0),
                        "breakdown": item.get("score", {}).get("breakdown", {}),
                    }
                )

    sections_available = sorted({item["section"] for item in items})
    speakers_available = sorted({item["speaker"] for item in items if item["speaker"]})

    section_filter = st.selectbox(
        "Section", options=["All"] + sections_available, key="highlights_section_filter"
    )
    speaker_filter = st.multiselect(
        "Speakers", options=speakers_available, key="highlights_speaker_filter"
    )
    min_score = st.slider(
        "Minimum score", min_value=0.0, max_value=1.0, value=0.0, step=0.05
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
        time_range = f"{format_time_detailed(item['start'])}-{format_time_detailed(item['end'])}"
        st.markdown(
            f"**{item['speaker']}** · {time_range} · score {item['score']:.3f}"
        )
        st.write(item["quote"])
        with st.expander("Score breakdown"):
            st.json(item["breakdown"])


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
        st.dataframe(rows, width='stretch')

