"""Home launchpad: what should I do next?"""

from __future__ import annotations

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.app.corpus_inventory.models import (
    ContinueAction,
    InventoryRow,
    LibraryFilter,
    LibraryWorkflowPreset,
)
from transcriptx.app.corpus_inventory.query import (
    continue_working_action,
    corpus_summary,
    needs_attention_counts,
    select_continue_working,
)
from transcriptx.utils.text_utils import format_duration_display_from_config
from transcriptx.web.action_menus.context import build_transcript_identity_with_run
from transcriptx.web.action_menus.services import navigate_with_identity
from transcriptx.web.cache_helpers import (
    cached_list_recent_runs,
    get_cached_corpus_inventory,
)
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.recent_run_row import render_recent_run_row
from transcriptx.web.corpus_inventory_display import format_relative_age
from transcriptx.web.navigation import navigate_to_library
from transcriptx.web.perf import instrument_cached_call, set_count
from transcriptx.web.sidebar_options import _slug_display_labels_from_index

_HOME_DESCRIPTION = (
    "Resume work and see what needs attention. Browse and filter the full "
    "corpus in Library."
)

_CONTINUE_PAGES = {
    ContinueAction.CORRECTIONS: ("Corrections", "Corrections Studio"),
    ContinueAction.SPEAKER_ID: ("Speaker ID", "Speaker ID"),
    ContinueAction.ANALYSE: ("Analyse", "Run Analysis"),
    ContinueAction.OPEN: ("Open", "Overview"),
}

_HOME_RECENT_ACTIVITY_EXPANDED = "home_recent_activity_expanded"
_RECENT_ACTIVITY_INITIAL = 3
_RECENT_ACTIVITY_MAX = 10


def _inventory_rows() -> list[InventoryRow]:
    rows = instrument_cached_call(
        "cached_corpus_inventory",
        get_cached_corpus_inventory,
        bucket="home_summary",
    )
    return list(rows or [])


def _render_corpus_summary(rows: list[InventoryRow]) -> None:
    summary = corpus_summary(rows)
    duration = format_duration_display_from_config(
        summary["total_duration_seconds"]
    )
    st.caption(
        f"{summary['transcript_count']} transcripts · "
        f"{summary['analysed_count']} analysed · {duration}"
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Transcripts", int(summary["transcript_count"]))
    with col2:
        st.metric("Analysed transcripts", int(summary["analysed_count"]))
    with col3:
        st.metric("Total duration", duration)


def _open_continue_item(row: InventoryRow) -> None:
    action = continue_working_action(row)
    _label, page = _CONTINUE_PAGES[action]
    identity = build_transcript_identity_with_run(
        subject_id=row.slug or row.transcript_path.stem,
        transcript_path=row.transcript_path,
        run_id=row.analysis.latest_run_id,
    )
    navigate_with_identity(identity, page)
    st.rerun()


def _render_continue_working(rows: list[InventoryRow]) -> None:
    st.subheader("Continue working")
    chosen = select_continue_working(rows, limit=5)
    if not chosen:
        st.caption("Nothing queued — import a transcript or pick up work in Library.")
        return
    for index, row in enumerate(chosen):
        action = continue_working_action(row)
        label, _page = _CONTINUE_PAGES[action]
        cols = st.columns([4, 1.2])
        with cols[0]:
            st.markdown(f"**{row.title}**")
            st.caption(format_relative_age(row.last_activity_at))
        with cols[1]:
            if st.button(
                label,
                key=f"home_continue_{index}_{row.transcript_path.stem}",
                icon=ic.ARROW_FORWARD,
            ):
                _open_continue_item(row)


def _render_needs_attention(rows: list[InventoryRow]) -> None:
    st.subheader("Needs attention")
    counts = needs_attention_counts(rows)
    items = [
        (
            counts["speaker_id"],
            "need Speaker ID",
            LibraryFilter(preset=LibraryWorkflowPreset.NEEDS_SPEAKER_ID),
        ),
        (
            counts["analysis"],
            "have incomplete analyses",
            LibraryFilter(preset=LibraryWorkflowPreset.FAILED_INCOMPLETE),
        ),
        (
            counts["corrections"],
            "correction sessions unfinished",
            LibraryFilter(preset=LibraryWorkflowPreset.CORRECTIONS_PENDING),
        ),
    ]
    if not any(count for count, _label, _filt in items):
        st.caption("No blockers right now.")
        return
    for count, label, library_filter in items:
        if not count:
            continue
        if st.button(
            f"{count} {label}",
            key=f"home_attention_{library_filter.preset.value}",
            icon=ic.TASK_ALT,
        ):
            navigate_to_library(st.session_state, library_filter=library_filter)
            st.rerun()


def _render_recent_activity() -> None:
    st.subheader("Recent activity")
    runs = instrument_cached_call(
        "cached_list_recent_runs",
        cached_list_recent_runs,
        limit=_RECENT_ACTIVITY_MAX,
        bucket="home_summary",
    )
    set_count("recent_runs_returned", len(runs))
    if not runs:
        st.caption("No analysis runs yet.")
        return
    expanded = bool(st.session_state.get(_HOME_RECENT_ACTIVITY_EXPANDED))
    show_n = _RECENT_ACTIVITY_MAX if expanded else _RECENT_ACTIVITY_INITIAL
    slug_labels = _slug_display_labels_from_index()
    for idx, run in enumerate(runs[:show_n]):
        render_recent_run_row(run, row_index=idx, slug_labels=slug_labels)
    if len(runs) > _RECENT_ACTIVITY_INITIAL and not expanded:
        if st.button(
            "Show more",
            key="home_recent_activity_show_more",
            icon=ic.SHOW_MORE,
        ):
            st.session_state[_HOME_RECENT_ACTIVITY_EXPANDED] = True
            st.rerun()


def render_home() -> None:
    """Render the home launchpad."""
    render_page_shell("Home", _HOME_DESCRIPTION)

    try:
        rows = _inventory_rows()
        if not rows:
            render_empty_state(
                "no_results_yet",
                "No transcripts found",
                "Add transcripts in Library to get started.",
                primary_action=("Import Transcript", "Import Transcript"),
                secondary_action=("Library", "Library"),
                primary_icon=ic.UPLOAD,
                secondary_icon=ic.LIBRARY,
            )
            return

        _render_corpus_summary(rows)
        _render_recent_activity()
        _render_needs_attention(rows)
        _render_continue_working(rows)
        if st.button(
            "Browse all transcripts",
            key="home_browse_library",
            icon=ic.LIBRARY,
        ):
            navigate_to_library(
                st.session_state,
                library_filter=LibraryFilter(preset=LibraryWorkflowPreset.ALL),
            )
            st.rerun()
    except Exception as e:
        st.error(f"Could not load dashboard: {e}")
