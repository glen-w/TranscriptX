"""Library page — corpus inventory and workflow-state browser."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from transcriptx.app.corpus_inventory.models import (
    InventoryRow,
    LibraryFilter,
    LibrarySort,
    LibraryWorkflowPreset,
)
from transcriptx.app.corpus_inventory.query import apply_library_filter
from transcriptx.core.analysis.voice.audio_io import resolve_audio_path
from transcriptx.core.utils.rename.audio_association import find_original_audio_file
from transcriptx.utils.text_utils import format_duration_display_from_config
from transcriptx.web.action_menus.context import (
    ActionContext,
    build_transcript_identity_with_run,
)
from transcriptx.web.action_menus.ids import ActionId, NavStyle, SectionId
from transcriptx.web.action_menus.render import (
    action_widget_key,
    render_action,
    render_configured_actions,
)
from transcriptx.web.action_menus.resolve import overflow_actions_for_section
from transcriptx.web.cache_helpers import get_cached_corpus_inventory
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.info_tooltip import widget_help
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.corpus_inventory_display import (
    format_analysis_label,
    format_corrections_label,
    format_short_date,
    format_speaker_id_label,
    inventory_table_row,
)
from transcriptx.web.navigation import consume_library_nav
from transcriptx.web.perf import instrument_cached_call
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.services.transcript_context_resolver import (
    paths_match,
    tolerant_resolve,
)
from transcriptx.web.state import (
    LIBRARY_FILTER_PRESET_KEY,
    LIBRARY_FILTER_QUERY_KEY,
    LIBRARY_FILTER_SORT_KEY,
    LIBRARY_FILTER_SOURCE_KEY,
    LIBRARY_SELECTED_TRANSCRIPT_PATH,
    LIBRARY_SHOW_PATH_KEY,
    LIBRARY_TABLE_EPOCH_KEY,
)

_LIBRARY_DESCRIPTION = (
    "Find and manage transcripts — what you have, what state they are in, "
    "and what to do next. Search titles here; use Search to find phrases "
    "inside transcripts."
)

_PRESET_LABELS: dict[LibraryWorkflowPreset, str] = {
    LibraryWorkflowPreset.ALL: "All",
    LibraryWorkflowPreset.UNANALYSED: "Unanalysed",
    LibraryWorkflowPreset.NEEDS_SPEAKER_ID: "Needs Speaker ID",
    LibraryWorkflowPreset.CORRECTIONS_PENDING: "Corrections pending",
    LibraryWorkflowPreset.ANALYSED: "Analysed",
    LibraryWorkflowPreset.FAILED_INCOMPLETE: "Failed / incomplete",
}

_SORT_LABELS: dict[LibrarySort, str] = {
    LibrarySort.RECENTLY_WORKED: "Recently worked on",
    LibrarySort.RECENTLY_ADDED: "Recently added",
    LibrarySort.NAME: "Name",
    LibrarySort.DURATION: "Duration",
    LibrarySort.ANALYSIS_COMPLETION: "Analysis completion",
}


_AUDIO_MIME_BY_SUFFIX = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".opus": "audio/opus",
    ".flac": "audio/flac",
    ".webm": "audio/webm",
}


def _audio_mime_for_path(path: Path) -> str:
    return _AUDIO_MIME_BY_SUFFIX.get(path.suffix.lower(), "audio/mpeg")


def _render_inspector_audio(transcript_path: Path) -> None:
    audio_path = _resolve_audio_for_transcript(transcript_path)
    if audio_path is None:
        st.caption("No linked audio")
        return
    st.audio(audio_path, format=_audio_mime_for_path(audio_path))


def _resolve_audio_for_transcript(transcript_path: Path) -> Path | None:
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


def _row_by_path(
    rows: list[InventoryRow], transcript_path: str | Path | None
) -> InventoryRow | None:
    if not transcript_path:
        return None
    target = tolerant_resolve(transcript_path)
    for row in rows:
        if paths_match(row.transcript_path, target):
            return row
    return None


def _current_library_filter() -> LibraryFilter:
    preset_raw = st.session_state.get(
        LIBRARY_FILTER_PRESET_KEY, LibraryWorkflowPreset.ALL.value
    )
    try:
        preset = LibraryWorkflowPreset(preset_raw)
    except ValueError:
        preset = LibraryWorkflowPreset.ALL
    sort_raw = st.session_state.get(
        LIBRARY_FILTER_SORT_KEY, LibrarySort.RECENTLY_WORKED.value
    )
    try:
        sort = LibrarySort(sort_raw)
    except ValueError:
        sort = LibrarySort.RECENTLY_WORKED
    source = st.session_state.get(LIBRARY_FILTER_SOURCE_KEY) or None
    if source in {"", "All"}:
        source = None
    return LibraryFilter(
        preset=preset,
        query=str(st.session_state.get(LIBRARY_FILTER_QUERY_KEY) or ""),
        sort=sort,
        source_id=source,
    )


def _selection_from_dataframe(event: object, visible: list[InventoryRow]) -> None:
    """Map a dataframe row click to path identity (never persist the row index)."""
    selection = getattr(event, "selection", None)
    rows = getattr(selection, "rows", None) or []
    if not rows:
        return
    try:
        idx = int(rows[0])
    except (TypeError, ValueError):
        return
    if 0 <= idx < len(visible):
        st.session_state[LIBRARY_SELECTED_TRANSCRIPT_PATH] = str(
            visible[idx].transcript_path
        )


@st.fragment
def _library_browser_fragment(rows: list[InventoryRow]) -> None:
    consume_library_nav(st.session_state)
    st.session_state.setdefault(
        LIBRARY_FILTER_PRESET_KEY, LibraryWorkflowPreset.ALL.value
    )
    st.session_state.setdefault(
        LIBRARY_FILTER_SORT_KEY, LibrarySort.RECENTLY_WORKED.value
    )
    current_path = SubjectService.current_transcript_path(st.session_state)
    if current_path and not st.session_state.get(LIBRARY_SELECTED_TRANSCRIPT_PATH):
        st.session_state[LIBRARY_SELECTED_TRANSCRIPT_PATH] = str(
            tolerant_resolve(current_path)
        )

    query_col, preset_col, sort_col = st.columns([2, 2, 1.4])
    with query_col:
        st.text_input(
            "Search transcripts",
            key=LIBRARY_FILTER_QUERY_KEY,
            placeholder="Title or filename",
            help=widget_help(
                "Filters the library by title or filename, not transcript text."
            ),
        )
    with preset_col:
        st.pills(
            "Workflow",
            options=[preset.value for preset in LibraryWorkflowPreset],
            format_func=lambda value: _PRESET_LABELS[LibraryWorkflowPreset(value)],
            key=LIBRARY_FILTER_PRESET_KEY,
            help=widget_help("Slice the corpus by workflow state."),
        )
    with sort_col:
        st.selectbox(
            "Sort",
            options=[item.value for item in LibrarySort],
            format_func=lambda value: _SORT_LABELS[LibrarySort(value)],
            key=LIBRARY_FILTER_SORT_KEY,
        )

    sources = sorted({row.source_id for row in rows if row.source_id})
    with st.expander("Property filters", expanded=False):
        st.selectbox(
            "Source",
            options=["All", *sources],
            key=LIBRARY_FILTER_SOURCE_KEY,
            help=widget_help("Import adapter / source type."),
        )

    library_filter = _current_library_filter()
    visible = apply_library_filter(rows, library_filter)
    st.caption(f"{len(visible)} of {len(rows)} transcripts")

    show_path = st.toggle(
        "Show path column",
        value=False,
        key=LIBRARY_SHOW_PATH_KEY,
        help=widget_help("Include the on-disk managed path in the library table."),
    )
    table = pd.DataFrame(
        [inventory_table_row(row, include_path=show_path) for row in visible]
    )
    event = st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"library_inventory_table_{int(st.session_state.get(LIBRARY_TABLE_EPOCH_KEY) or 0)}",
    )
    _selection_from_dataframe(event, visible)

    selected = _row_by_path(
        rows, st.session_state.get(LIBRARY_SELECTED_TRANSCRIPT_PATH)
    )
    if selected is None:
        return

    SubjectService.set_transcript_context_from_path(
        st.session_state,
        selected.transcript_path,
        linked_run_dirs=[],
    )
    _render_inspector(selected)


def _render_inspector(selected: InventoryRow) -> None:
    st.divider()
    st.subheader(selected.title)
    duration = format_duration_display_from_config(selected.duration_seconds)
    speakers = (
        "—" if selected.speaker_count is None else f"{selected.speaker_count} speakers"
    )
    words = (
        f"{selected.word_count:,} words"
        if selected.word_count is not None
        else "— words"
    )
    st.caption(f"{duration} · {speakers} · {words}")
    _render_inspector_audio(selected.transcript_path)
    st.caption(f"Speaker identification: {format_speaker_id_label(selected.speaker)}")
    st.caption(f"Corrections: {format_corrections_label(selected.corrections)}")
    st.caption(f"Analysis: {format_analysis_label(selected.analysis)}")
    last_analysed = format_short_date(selected.analysis.last_analysed_at)
    st.caption(f"Last analysed: {last_analysed}")

    subject_id = selected.slug or selected.transcript_path.stem
    identity = build_transcript_identity_with_run(
        subject_id=subject_id,
        transcript_path=selected.transcript_path,
        run_id=selected.analysis.latest_run_id,
    )
    ctx = ActionContext(
        identity=identity,
        widget_identity=f"lib_{subject_id}",
        nav_style=NavStyle.CLICK_RERUN,
        instance_prefix="lib",
        rename_supported=True,
        export_supported=selected.analysis.latest_run_id is not None,
        run_completed=selected.analysis.status.value == "completed",
    )
    primary = render_configured_actions(SectionId.LIBRARY_SELECTED, ctx)
    overflow = overflow_actions_for_section(
        SectionId.LIBRARY_SELECTED,
        ctx,
        primary,
        exclude=frozenset({ActionId.EXPORT_ZIP}),
    )
    with st.popover("⋯"):
        st.caption(f"Path: {selected.transcript_path}")
        audio_path = _resolve_audio_for_transcript(selected.transcript_path)
        st.caption(f"Audio: {'✓' if audio_path is not None else '—'}")
        for action in overflow:
            key = action_widget_key(
                instance_prefix=ctx.instance_prefix,
                section=SectionId.LIBRARY_SELECTED,
                widget_identity=f"{ctx.widget_identity}_more",
                action=action,
            )
            render_action(action, ctx, section=SectionId.LIBRARY_SELECTED, key=key)


def render_library() -> None:
    """Render the transcript library page."""
    render_page_shell(
        "Library",
        _LIBRARY_DESCRIPTION,
        actions=None,
    )

    try:
        rows = instrument_cached_call(
            "cached_corpus_inventory",
            get_cached_corpus_inventory,
            bucket="transcript_discovery",
        )
        if not rows:
            render_empty_state(
                "no_results_yet",
                "No transcripts found",
                "Add transcript JSON files to your configured transcript folder.",
                primary_action=("Import Transcript", "Import Transcript"),
                secondary_action=("Transcribe Audio", "Transcribe Audio"),
            )
            return
        _library_browser_fragment(rows)
    except Exception as e:
        st.error(f"Could not load library: {e}")
