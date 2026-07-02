"""
Library page - browse transcripts and audio inputs.

First paint: render_page_shell() then transcript index discovery via
get_cached_list_transcripts(). Detailed summary enrichment stays behind the
"Show detailed metadata" toggle.

Table toggle and selection widgets run in ``@st.fragment`` so they do not trigger
a full-app rerun.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import streamlit as st
import pandas as pd

from transcriptx.core.analysis.voice.audio_io import resolve_audio_path
from transcriptx.core.utils.file_rename import find_original_audio_file
from transcriptx.web.cache_helpers import (
    cached_get_transcript_summaries_for_paths,
    get_cached_list_transcripts,
)
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.rename_form import render_transcript_rename_form
from transcriptx.web.perf import instrument_cached_call
from transcriptx.web.state import (
    SELECTBOX_PLACEHOLDER_TRANSCRIPT,
    SELECTED_TRANSCRIPT_PATH,
)
from transcriptx.web.navigation import (
    apply_transcript_selection_context,
    consume_library_transcript_nav,
    library_transcript_index,
)
from transcriptx.utils.text_utils import format_duration_display_from_config


def _format_path_created_at(path: Path) -> str:
    """Return file created timestamp when available."""
    try:
        stats = path.stat()
    except OSError:
        return "—"
    timestamp = getattr(stats, "st_birthtime", stats.st_ctime)
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _resolve_audio_for_transcript(transcript_path: Path) -> Path | None:
    """Resolve linked audio file path for a transcript, if present."""
    try:
        candidate = find_original_audio_file(str(transcript_path))
        if candidate:
            candidate_path = Path(candidate)
            if candidate_path.exists():
                return candidate_path
    except Exception:
        pass
    try:
        resolved = resolve_audio_path(
            transcript_path=str(transcript_path), output_dir=None
        )
        if resolved:
            resolved_path = Path(resolved)
            if resolved_path.exists():
                return resolved_path
    except Exception:
        pass
    return None


def _speaker_stats_for_path(
    summary_by_path: dict[str, object],
    transcript_path: Path,
    fallback_total: int | None,
) -> tuple[str, str, str]:
    """
    Return (fully_mapped_mark, identified_count, ignored_count) for the table row.

    Values are derived from Speaker Studio transcript summaries so Library and
    Speaker ID use the same completeness semantics.
    """
    summary = summary_by_path.get(str(transcript_path.resolve()))
    if summary is None:
        return "—", "-", "-"

    status = str(getattr(summary, "speaker_map_status", "none") or "none")
    fully_mapped = "✓" if status == "complete" else "—"
    ignored = int(getattr(summary, "ignored_speaker_count", 0) or 0)
    unidentified = int(getattr(summary, "unidentified_speaker_count", 0) or 0)
    total = fallback_total
    if total is None:
        total = int(getattr(summary, "unique_speaker_count", 0) or 0)
    identified = max(int(total or 0) - ignored - unidentified, 0)
    return fully_mapped, str(identified), str(ignored)


def _build_library_rows(transcripts: list) -> list[dict[str, str]]:
    rows = []
    for m in transcripts:
        transcript_path = Path(m.path)
        rows.append(
            {
                "Name": m.base_name,
                "Path": str(transcript_path),
                "Date Created": _format_path_created_at(transcript_path),
                "Speakers": ("-" if m.speaker_count is None else str(m.speaker_count)),
                "Duration": format_duration_display_from_config(m.duration_seconds),
            }
        )
    return rows


def _load_selected_transcript_summary(selected_path: Path) -> object | None:
    summaries = instrument_cached_call(
        "cached_get_transcript_summaries_for_paths",
        cached_get_transcript_summaries_for_paths,
        (str(selected_path.resolve()),),
        bucket="segment_metadata_load",
    )
    return summaries[0] if summaries else None


@st.fragment
def _library_browser_fragment(transcripts: list) -> None:
    """Transcript table and actions without full-app rerun."""
    rows = _build_library_rows(transcripts)
    df = pd.DataFrame(rows)
    show_path_col = st.toggle("Show path column", value=False, key="library_show_path")
    show_detailed_metadata = st.toggle(
        "Show detailed metadata",
        value=False,
        key="library_show_detailed_metadata",
    )
    display_df = df if show_path_col else df.drop(columns=["Path"])
    if show_detailed_metadata:
        st.caption("Detailed metadata loads after you select a transcript.")
    st.dataframe(
        display_df,
        width="stretch",
        hide_index=True,
    )

    st.divider()
    st.subheader("Selected Transcript")
    consume_library_transcript_nav(st.session_state, transcripts)
    selected_path = st.session_state.get(SELECTED_TRANSCRIPT_PATH)
    default_idx = (
        library_transcript_index(transcripts, selected_path) if selected_path else 0
    )
    selected_idx = st.selectbox(
        "Select transcript",
        range(len(transcripts) + 1),
        format_func=lambda i: (
            SELECTBOX_PLACEHOLDER_TRANSCRIPT if i == 0 else transcripts[i - 1].base_name
        ),
        index=default_idx,
        key="library_transcript_select",
    )
    if selected_idx == 0:
        render_empty_state(
            "missing_prerequisite",
            "Select a transcript",
            "Choose one transcript to load detailed metadata and actions.",
            primary_action=("Run Analysis", "Run Analysis"),
            secondary_action=("Speaker ID", "Speaker ID"),
        )
        return

    selected = transcripts[selected_idx - 1]
    apply_transcript_selection_context(st.session_state, str(selected.path))
    st.caption(f"Path: {selected.path}")
    st.caption(
        f"Duration: {format_duration_display_from_config(selected.duration_seconds)}"
    )
    st.caption(
        f"Speakers: {'-' if selected.speaker_count is None else selected.speaker_count}"
    )

    if show_detailed_metadata:
        summary = _load_selected_transcript_summary(Path(selected.path))
        fully_mapped, identified_count, ignored_count = _speaker_stats_for_path(
            (
                {str(Path(selected.path).resolve()): summary}
                if summary is not None
                else {}
            ),
            Path(selected.path),
            selected.speaker_count,
        )
        audio_path = _resolve_audio_for_transcript(Path(selected.path))
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(f"Has Audio: {'✓' if audio_path is not None else '—'}")
            st.caption(f"Has Analysis: {'✓' if selected.has_analysis_outputs else '—'}")
        with col2:
            st.caption(f"Fully Mapped: {fully_mapped}")
            st.caption(f"Identified: {identified_count}")
        with col3:
            st.caption(f"Ignored: {ignored_count}")
            st.caption(
                f"Date Recorded: {_format_path_created_at(audio_path) if audio_path else '—'}"
            )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Run Speaker ID", key="lib_speaker_id"):
            st.session_state["page"] = "Speaker ID"
            st.rerun()
    with col2:
        if st.button("Run Analysis", key="lib_run_analysis"):
            st.session_state["page"] = "Run Analysis"
            st.rerun()

    render_transcript_rename_form(
        selected.path,
        form_key="library_rename_form",
        library_transcripts=transcripts,
    )


def render_library() -> None:
    """Render the transcript library page."""
    render_page_shell(
        "Library",
        "Browse transcripts quickly, then load detailed metadata only for the selected transcript.",
        actions=None,
    )

    try:
        transcripts = instrument_cached_call(
            "cached_list_transcripts",
            get_cached_list_transcripts,
            bucket="transcript_discovery",
        )

        if not transcripts:
            render_empty_state(
                "no_results_yet",
                "No transcripts found",
                "Add transcript JSON files to your configured transcript folder.",
                primary_action=("Import Transcript", "Import Transcript"),
                secondary_action=("Transcribe Audio", "Transcribe Audio"),
            )
            return
        _library_browser_fragment(transcripts)

    except Exception as e:
        st.error(f"Could not load library: {e}")
