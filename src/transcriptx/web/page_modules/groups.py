"""
Group management page for TranscriptX Studio.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from transcriptx.core.pipeline.module_registry import get_default_modules  # type: ignore[import]
from transcriptx.core.pipeline.pipeline import run_analysis_pipeline  # type: ignore[import]
from transcriptx.core.pipeline.target_resolver import GroupRef
from transcriptx.core.utils.paths import GROUP_OUTPUTS_DIR  # type: ignore[import]
from transcriptx.web.services.group_service import GroupService  # type: ignore[import]

def _list_group_runs(group_uuid: str) -> list[Path]:
    base_dir = Path(GROUP_OUTPUTS_DIR) / group_uuid
    if not base_dir.exists():
        return []
    return sorted(
        [p for p in base_dir.iterdir() if p.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def _render_group_artifacts(run_dir: Path) -> None:
    combined_dir = run_dir / "combined"
    if not combined_dir.exists():
        st.info("No aggregated outputs found for this run.")
        return

    summaries = [
        ("Stats", combined_dir / "stats_group_summary.json"),
        ("Sentiment", combined_dir / "sentiment_group_summary.json"),
        ("Emotion", combined_dir / "emotion_group_summary.json"),
        ("Interactions", combined_dir / "interactions_group_summary.json"),
    ]
    for label, path in summaries:
        if not path.exists():
            continue
        with st.expander(f"{label} Summary"):
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            st.json(data)


def render_groups() -> None:
    st.markdown('<div class="main-header">Groups</div>', unsafe_allow_html=True)

    groups = GroupService.list_groups()
    if not groups:
        st.info("No TranscriptSets found. Create a group via CLI or database tools.")
        return

    options = {g.uuid: g for g in groups}
    labels = {
        g.uuid: f"{g.name or 'Unnamed'} • {len(g.transcript_file_uuids or [])} transcripts"
        for g in groups
    }

    selected_id = st.selectbox(
        "Select Group",
        list(options.keys()),
        format_func=lambda key: labels.get(key, key),
    )
    group = options[selected_id]

    st.subheader("Group Details")
    st.write(f"**UUID:** {group.uuid}")
    if group.name:
        st.write(f"**Name:** {group.name}")
    st.write(f"**Type:** {group.type}")
    st.write(f"**Transcript count:** {len(group.transcript_file_uuids or [])}")
    st.write(f"**Group key:** {group.key}")

    with st.expander("Transcript UUIDs", expanded=False):
        for transcript_uuid in group.transcript_file_uuids or []:
            st.write(f"- {transcript_uuid}")

    members = GroupService.get_members(group)
    if members:
        with st.expander("Transcript files", expanded=False):
            for member in members:
                st.write(f"- {member.file_path}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Re-analyze group"):
            with st.spinner("Running group analysis..."):
                transcript_paths = (
                    [m.file_path for m in members if m.file_path] if members else []
                )
                run_analysis_pipeline(
                    target=GroupRef(group_uuid=group.uuid),
                    selected_modules=get_default_modules(transcript_paths, for_group=True),
                )
            st.success("Group analysis completed.")
    with col2:
        if st.button("Delete group", type="secondary"):
            GroupService.delete_group(group.uuid)
            st.success("Group deleted.")
            st.rerun()

    st.subheader("Group Runs")
    runs = _list_group_runs(group.uuid)
    if not runs:
        st.info("No group runs found for this TranscriptSet.")
        return

    run_options = {run.name: run for run in runs}
    selected_run = st.selectbox(
        "Select run",
        list(run_options.keys()),
    )
    run_dir = run_options[selected_run]
    st.caption(f"Run directory: {run_dir}")
    _render_group_artifacts(run_dir)
