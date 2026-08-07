"""Transcript page module.

Search/timestamp controls and segment tabs run in ``@st.fragment`` so toggling them
does not reload the full transcript and sidebar.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import streamlit as st

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger
from transcriptx.utils.text_utils import format_duration_display_from_config
from transcriptx.web.components.action_links import render_action_link
from transcriptx.web.components.empty_state import render_empty_state
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.playback_panel import (
    PlaybackAvailability,
    PlaybackUnavailableReason,
    clear_playback_session_keys,
    render_active_clip,
    render_playback_unavailable,
    resolve_playback_availability,
    trigger_clip_warm,
)
from transcriptx.web.models.search import NavRequest, SegmentRef
from transcriptx.web.services import FileService, RunIndex, SubjectService
from transcriptx.web.speaker_studio_runtime import get_shared_speaker_studio_controller
from transcriptx.web.state import (
    NAV_REQUEST_KEY,
    PAGE_KEY,
)
from transcriptx.web.transcript_view_state import (
    consume_nav_request,
    filtered_display_segments,
    resolve_transcript_artifacts,
)
from transcriptx.web.transcript_viewer.downloads import render_download_row
from transcriptx.web.transcript_viewer.metadata import (
    segment_word_stats,
    speaker_tooltip,
)
from transcriptx.web.transcript_viewer.playback_targets import (
    build_playback_targets,
    filtered_view_signature,
    ordered_playback_targets,
    owner_prefix_hash,
    transcript_revision_identity,
    warm_list_position,
)
from transcriptx.web.transcript_viewer.preflight import (
    ViewerPreflight,
    resolve_viewer_preflight,
)
from transcriptx.web.transcript_viewer.segments import (
    TranscriptPlaybackBinding,
    render_plain_segments,
    render_segmented_tab,
)
from transcriptx.web.utils import (
    list_available_sessions,
    load_transcript_with_path_by_session,
    resolve_speaker_names_from_db,
)

logger = get_logger()

_PLAY_KEY = "transcript_viewer_play_seg"
_OWNER_KEY = "transcript_viewer_play_owner"
_VIEW_SIG_KEY = "transcript_viewer_play_view_sig"
_WARM_SIG_SUFFIX = "_warm_sig"


@dataclass(frozen=True)
class TranscriptControlsState:
    search_text: str
    show_timestamps: bool
    format_key: str
    show_unnamed_speakers: bool


def navigate_to_segment(
    segment_ref: SegmentRef, highlight_query: str | None = None
) -> None:
    """Jump from search results into Transcript page context and rerun."""
    from transcriptx.web.state import apply_subject_context

    apply_subject_context(
        st.session_state,
        subject_type="transcript",
        subject_id=segment_ref.transcript_ref.session_slug,
        run_id=segment_ref.transcript_ref.run_id,
    )
    st.session_state[PAGE_KEY] = "Transcript"
    st.session_state[NAV_REQUEST_KEY] = NavRequest(
        segment_ref=segment_ref,
        highlight_query=highlight_query,
    )
    st.rerun()


def _render_group_browser(subject) -> None:
    """Render group member selector and switch context to transcript on click."""
    st.subheader("Group transcripts")
    if not subject.members:
        st.info("This group has no transcripts.")
        return
    st.caption("Select a transcript to open its viewer.")
    sessions = list_available_sessions()
    for index, member in enumerate(subject.members, start=1):
        display_name = (
            member.file_name
            or (Path(member.file_path).name if member.file_path else None)
            or "(unknown)"
        )
        numbered_name = f"{index}. {display_name}"
        session_info = FileService.resolve_session_for_transcript_path(
            member.file_path, sessions
        )
        if session_info:
            session_slug, session_run_id = session_info
            member_key = member.uuid or f"index_{index}"
            if render_action_link(
                f"View: {numbered_name}",
                key=f"group_member_transcript_{member_key}",
                icon=":material/article:",
            ):
                from transcriptx.web.state import apply_subject_context

                apply_subject_context(
                    st.session_state,
                    subject_type="transcript",
                    subject_id=session_slug,
                    run_id=session_run_id,
                )
                st.session_state[PAGE_KEY] = "Transcript"
                st.rerun()
        else:
            st.caption(f"{numbered_name} (session not found)")


def _render_preflight_empty_state(preflight: ViewerPreflight) -> None:
    """Render preflight empty states without mutating navigation context."""
    if preflight.status == "no_subject":
        render_empty_state(
            "missing_prerequisite",
            "No subject selected",
            "Choose a transcript or group in the sidebar, then pick a run.",
            primary_action=("Open Library", "Library"),
            secondary_action=("Run Analysis", "Run Analysis"),
        )
    elif preflight.status == "wrong_subject":
        render_empty_state(
            "missing_prerequisite",
            "Transcript view needs a transcript subject",
            "Switch the sidebar context to **Transcript** or open a member from **Groups**.",
            primary_action=("Groups", "Groups"),
            secondary_action=("Overview", "Overview"),
        )
    elif preflight.status == "no_run":
        render_empty_state(
            "missing_prerequisite",
            "No run selected",
            "Select a run for this transcript in the sidebar.",
            primary_action=("Run Analysis", "Run Analysis"),
            secondary_action=("Overview", "Overview"),
        )
    else:
        render_empty_state(
            "missing_prerequisite",
            "Transcript context unavailable",
            "Select a transcript and run in the sidebar.",
            primary_action=("Overview", "Overview"),
            secondary_action=("Library", "Library"),
        )


def _render_metadata_metrics(
    transcript_data: dict, segments: list[dict[str, Any]] | None = None
) -> None:
    """Render top-level transcript metadata metrics.

    Prefer resolved ``segments`` (with mapped speaker names) for the Speakers
    tooltip; fall back to raw transcript segments when not provided.
    """
    metadata = transcript_data.get("metadata", {})
    if segments is None:
        segments = transcript_data.get("segments", []) or []
    speaker_help = speaker_tooltip(segments)
    seg_count, total_words, avg_words = segment_word_stats(segments)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Duration",
            format_duration_display_from_config(metadata.get("duration_seconds", 0)),
        )
    with col2:
        st.metric("Speakers", metadata.get("speaker_count", 0), help=speaker_help)
    with col3:
        st.metric(
            "Segments",
            seg_count,
            help=f"Total words: {total_words:,}\nAverage words/segment: {avg_words:.1f}",
        )
    with col4:
        st.metric("Language", metadata.get("language", "Unknown"))


def _render_transcript_controls() -> TranscriptControlsState:
    """Render search and timestamp controls with existing widget keys.

    Do not wrap widgets in ``st.markdown`` open/close ``<div>`` tags: Streamlit
    cannot nest widgets inside markdown HTML, so an empty styled div renders as
    a thick white horizontal bar (especially with a light fallback background).
    """
    search_text = st.text_input("🔍 Search in transcript", key="transcript_search")
    show_timestamps = st.checkbox("Show timestamps", key="show_timestamps")
    show_unnamed_speakers = st.checkbox(
        "Show unnamed speakers",
        key="show_unnamed_speakers",
        help=(
            "Include diarization placeholders such as SPEAKER_02. "
            "Default comes from dashboard.transcript_exclude_unnamed_speakers."
        ),
    )
    format_key = st.session_state.get("timestamp_format", "seconds")
    return TranscriptControlsState(
        search_text=search_text,
        show_timestamps=show_timestamps,
        format_key=format_key,
        show_unnamed_speakers=show_unnamed_speakers,
    )


def _resolve_and_prepare_segments(
    transcript_data: dict[str, Any], selected_session: str
) -> list[dict[str, Any]]:
    """Resolve speaker names for transcript segments and return segment list."""
    segments = transcript_data.get("segments", [])
    if segments:
        segments = resolve_speaker_names_from_db(segments, selected_session)
    return segments


def _playback_owner_identity(
    *,
    session_slug: str,
    run_id: str,
    transcript_path: str,
    size: int,
    mtime_ns: int,
) -> tuple[str, str, str, int, int]:
    return (session_slug, run_id, transcript_path, size, mtime_ns)


def _owner_prefix(owner: tuple[Any, ...]) -> str:
    return owner_prefix_hash(owner)


def reset_transcript_playback_state_if_needed(
    session_state: dict[str, Any],
    *,
    owner: tuple[Any, ...],
    view_signature: tuple[Any, ...],
    targets: dict[int, Any],
) -> None:
    """
    Clear active play / warm state when owner or filtered view changes.

    Must run before widgets that use related keys.
    """
    prev_owner = session_state.get(_OWNER_KEY)
    prev_sig = session_state.get(_VIEW_SIG_KEY)
    if prev_owner != owner or prev_sig != view_signature:
        session_state[_PLAY_KEY] = None
        session_state[f"{_PLAY_KEY}{_WARM_SIG_SUFFIX}"] = None
        session_state[_OWNER_KEY] = owner
        session_state[_VIEW_SIG_KEY] = view_signature

    active = session_state.get(_PLAY_KEY)
    if active is not None and (type(active) is not int or active not in targets):
        session_state[_PLAY_KEY] = None
        session_state[f"{_PLAY_KEY}{_WARM_SIG_SUFFIX}"] = None


def _resolve_canonical_transcript_path(
    loaded_path: Path | None,
    artifacts_json: Path | None,
) -> Path | None:
    """Prefer the path used to load; fall back to artifacts.json_file.

    Attempts each candidate independently with ``resolve(strict=True)`` so a
    present-but-missing ``loaded_path`` still falls back to artifacts.
    """
    for candidate in (loaded_path, artifacts_json):
        if candidate is None:
            continue
        try:
            return candidate.resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
    return None


def _setup_playback_availability(
    transcript_path: Path | None,
) -> PlaybackAvailability:
    """Optional enrichment: never raise into the page-wide exception handler."""
    if transcript_path is None:
        return PlaybackAvailability(
            enabled=False,
            audio_path=None,
            reason=PlaybackUnavailableReason.transcript_unresolved,
        )
    try:
        controller = get_shared_speaker_studio_controller()
        return resolve_playback_availability(transcript_path, controller)
    except Exception:
        logger.warning(
            "Playback setup failed for transcript=%s",
            transcript_path,
            exc_info=True,
        )
        return PlaybackAvailability(
            enabled=False,
            audio_path=None,
            reason=PlaybackUnavailableReason.controller_error,
        )


def _seed_transcript_tab_widget(key: str, current: str, labels: list[str]) -> None:
    """Initialize or repair a keyed tab widget without pairing default=/index=."""
    # Streamlit warns if a widget key is written via Session State *and* default=
    # (or index=) is passed on the same instantiation. Chapter Jump/Play writes
    # these keys before the widget exists, so seed here and omit defaults.
    if key not in st.session_state or st.session_state.get(key) not in labels:
        st.session_state[key] = current


def _render_transcript_tab_nav(*, has_chapters: bool) -> str:
    """Programmable section nav (Insights-style) so Jump/Play can select Segments."""
    from transcriptx.web.transcript_viewer.chapters import (
        TRANSCRIPT_TAB_CONTROL_KEY,
        TRANSCRIPT_TAB_KEY,
    )

    options = [("turns", "Turns"), ("segments", "Segments")]
    if has_chapters:
        options.append(("chapters", "Chapters"))
    labels = [label for _, label in options]
    current = st.session_state.get(TRANSCRIPT_TAB_KEY, "turns")
    if current not in {key for key, _ in options}:
        current = "turns"
        st.session_state[TRANSCRIPT_TAB_KEY] = current
    default_label = dict(options)[current]
    _seed_transcript_tab_widget(TRANSCRIPT_TAB_CONTROL_KEY, default_label, labels)
    try:
        choice = st.segmented_control(
            "Transcript view",
            options=labels,
            key=TRANSCRIPT_TAB_CONTROL_KEY,
            label_visibility="collapsed",
        )
    except Exception:
        radio_key = "transcript_viewer_tab_radio"
        _seed_transcript_tab_widget(radio_key, default_label, labels)
        choice = st.radio(
            "Transcript view",
            labels,
            horizontal=True,
            key=radio_key,
            label_visibility="collapsed",
        )
    selected_key = next(k for k, lab in options if lab == choice)
    st.session_state[TRANSCRIPT_TAB_KEY] = selected_key
    return selected_key


def _render_chapters_panel(chapter_rows: list[Any]) -> None:
    from transcriptx.web.transcript_viewer.chapters import (
        format_chapter_time_range,
        queue_chapter_jump,
    )

    if not chapter_rows:
        st.caption("No topic-shift chapters for this run.")
        return
    st.caption(
        "Topic-shift chapters. Jump highlights that spot in the full transcript; "
        "Play also starts that clip."
    )
    for row in chapter_rows:
        cols = st.columns([4, 2, 1, 1])
        with cols[0]:
            label = row.title
            st.markdown(f"**{label}**")
            keywords = getattr(row, "keywords", ()) or ()
            # Title is often the first N keyword hints; skip the near-duplicate list.
            # Still show keywords when the title is an LLM/fallback phrase.
            if keywords:
                title_parts = [p.strip() for p in str(label).split("·") if p.strip()]
                kw_lower = {str(k).strip().lower() for k in keywords}
                title_is_keyword_built = bool(title_parts) and all(
                    p.lower() in kw_lower for p in title_parts
                )
                if not title_is_keyword_built:
                    st.caption(" · ".join(keywords))
            if row.summary:
                st.caption(row.summary[:240])
            meta = format_chapter_time_range(row.time_start, row.time_end)
            if row.strength is not None and row.leading_boundary_id:
                meta += f" · strength {row.strength:.2f}"
            st.caption(meta)
        target = row.viewer_target_source_index
        with cols[2]:
            if target is not None and st.button(
                "Jump",
                key=f"tx_chapter_jump_{row.span_id}",
                use_container_width=True,
            ):
                queue_chapter_jump(
                    st.session_state, source_index=int(target), play=False
                )
                st.rerun(scope="fragment")
        with cols[3]:
            if target is not None and st.button(
                "Play",
                key=f"tx_chapter_play_{row.span_id}",
                use_container_width=True,
            ):
                queue_chapter_jump(
                    st.session_state, source_index=int(target), play=True
                )
                st.rerun(scope="fragment")


def _render_transcript_tabs(
    display_segments: list[tuple[int, dict[str, Any]]],
    *,
    controls: TranscriptControlsState,
    highlight_query: str | None,
    jump_index: int | None,
    playback: TranscriptPlaybackBinding | None,
    chapter_rows: list[Any] | None = None,
) -> None:
    """Render turns/segments/chapters views for already-filtered display segments."""
    has_chapters = bool(chapter_rows)
    selected = _render_transcript_tab_nav(has_chapters=has_chapters)
    if selected == "turns":
        render_segmented_tab(
            display_segments,
            show_timestamps=controls.show_timestamps,
            format_key=controls.format_key,
            playback=playback,
        )
    elif selected == "segments":
        render_plain_segments(
            display_segments,
            show_timestamps=controls.show_timestamps,
            format_key=controls.format_key,
            highlight_query=highlight_query,
            jump_index=jump_index,
            playback=playback,
        )
    elif selected == "chapters":
        _render_chapters_panel(chapter_rows or [])


@st.fragment
def _transcript_interaction_fragment(
    segments: list[dict[str, Any]],
    *,
    highlight_query: str | None,
    jump_index: int | None,
    session_slug: str,
    run_id: str,
    transcript_path: str | None,
    transcript_size: int,
    transcript_mtime_ns: int,
    playback_availability: PlaybackAvailability,
    run_root: Path | None = None,
) -> None:
    """Transcript search and segment tabs without full-app rerun."""
    from transcriptx.web.transcript_viewer.chapters import (
        apply_deferred_chapter_jump,
        clear_chapter_jump,
        consume_chapter_pending,
        consume_scroll_to_jump,
        load_chapter_rows,
        sticky_chapter_jump,
    )
    from transcriptx.web.transcript_viewer.segments import scroll_jump_target_into_view

    # Jump/Play deferred widget writes must land before search/tab instantiate.
    apply_deferred_chapter_jump(st.session_state)
    controls = _render_transcript_controls()
    pending = consume_chapter_pending(st.session_state)
    sticky = sticky_chapter_jump(st.session_state)
    # Typing a search query takes over; drop the sticky chapter highlight.
    if controls.search_text and sticky is not None:
        clear_chapter_jump(st.session_state)
        sticky = None
    effective_jump = sticky if sticky is not None else jump_index
    if pending and isinstance(pending.get("jump_index"), int):
        effective_jump = int(pending["jump_index"])
    should_scroll = consume_scroll_to_jump(st.session_state)

    display_segments, filter_caption = filtered_display_segments(
        segments=segments,
        search_text=controls.search_text,
        jump_index=effective_jump,
        exclude_unnamed_speakers=not controls.show_unnamed_speakers,
    )
    if filter_caption:
        st.caption(filter_caption)
    owner = _playback_owner_identity(
        session_slug=session_slug,
        run_id=run_id,
        transcript_path=transcript_path or "",
        size=transcript_size,
        mtime_ns=transcript_mtime_ns,
    )
    targets = build_playback_targets(display_segments)
    view_sig = filtered_view_signature(
        owner_identity=owner,
        display_segments=display_segments,
        search_text=controls.search_text,
        jump_index=effective_jump,
    )
    reset_transcript_playback_state_if_needed(
        st.session_state,
        owner=owner,
        view_signature=view_sig,
        targets=targets,
    )
    # Re-apply chapter play after view-signature reset clears _PLAY_KEY.
    if pending and pending.get("play"):
        target = pending.get("jump_index")
        if type(target) is int and target in targets:
            st.session_state[_PLAY_KEY] = target

    playback_enabled = bool(
        playback_availability.enabled
        and transcript_path
        and playback_availability.audio_path is not None
        and targets
    )
    # Empty search: clear active, skip warm, still render tabs.
    if not display_segments:
        clear_playback_session_keys(_PLAY_KEY)
        playback_enabled = False

    if not playback_availability.enabled and playback_availability.reason is not None:
        clear_playback_session_keys(_PLAY_KEY)
        render_playback_unavailable(playback_availability.reason)
    elif playback_availability.enabled and display_segments and not targets:
        clear_playback_session_keys(_PLAY_KEY)
        render_playback_unavailable(PlaybackUnavailableReason.timing_unavailable)
    elif playback_enabled and transcript_path and playback_availability.audio_path:
        try:
            controller = get_shared_speaker_studio_controller()
            ordered = ordered_playback_targets(display_segments, targets)
            active_source = st.session_state.get(_PLAY_KEY)
            if type(active_source) is not int:
                active_source = None
            warm_pos = warm_list_position(ordered, active_source)
            trigger_clip_warm(
                controller,
                transcript_path,
                playback_availability.audio_path,
                ordered,
                warm_pos if warm_pos is not None else None,
                active_id=_owner_prefix(owner),
                play_key=_PLAY_KEY,
            )
            active_seg = (
                targets.get(active_source) if active_source is not None else None
            )
            render_active_clip(
                controller,
                transcript_path,
                active_seg,
                autoplay=True,
            )
        except Exception:
            logger.warning(
                "Playback rendering failed for transcript=%s; continuing text-only",
                transcript_path,
                exc_info=True,
            )
            clear_playback_session_keys(_PLAY_KEY)
            render_playback_unavailable(PlaybackUnavailableReason.controller_error)
            playback_enabled = False

    binding: TranscriptPlaybackBinding | None = None
    if playback_enabled:
        binding = TranscriptPlaybackBinding(
            enabled=True,
            targets=targets,
            play_key=_PLAY_KEY,
            owner_prefix=_owner_prefix(owner),
        )

    chapter_rows = load_chapter_rows(run_root) if run_root is not None else []
    _render_transcript_tabs(
        display_segments,
        controls=controls,
        highlight_query=highlight_query,
        jump_index=effective_jump,
        playback=binding,
        chapter_rows=chapter_rows,
    )
    if should_scroll and effective_jump is not None:
        scroll_jump_target_into_view()


def render_transcript_viewer() -> None:
    """Transcript viewer page."""
    render_page_shell(
        "Transcript",
        (
            "Read diarized segments for the current run. Search filters the list; "
            "use Turns for speaker blocks or Segments for line-by-line reading."
        ),
        badges=None,
        actions=None,
    )
    st.session_state.setdefault("show_timestamps", True)
    st.session_state.setdefault("timestamp_format", "seconds")
    exclude_unnamed = bool(
        get_config().dashboard.transcript_exclude_unnamed_speakers
    )
    st.session_state.setdefault("show_unnamed_speakers", not exclude_unnamed)
    if st.session_state.get("timestamp_format") == "real_time":
        st.session_state["timestamp_format"] = "seconds"
    try:
        preflight = resolve_viewer_preflight(
            st.session_state,
            resolve_subject=SubjectService.resolve_current_subject,
            get_run_root=lambda scope, run_id, subject_id: RunIndex.get_run_root(
                scope, run_id, subject_id=subject_id
            ),
        )
        if preflight.status == "group_browser":
            _render_group_browser(preflight.subject)
            return
        if preflight.status != "ok":
            _render_preflight_empty_state(preflight)
            return
        context = preflight.context_result
        selected = context.selected_session if context else None
        run_root = context.run_root if context else None
        run_id = context.run_id if context else None
        session_slug = context.session_slug if context else None
        if not selected or not run_root or not run_id or not session_slug:
            _render_preflight_empty_state(
                ViewerPreflight(status="context_failed", context_result=context)
            )
            return

        with st.spinner(f"Loading transcript for {selected}..."):
            loaded = load_transcript_with_path_by_session(selected)
        if not loaded:
            st.error(f"Transcript not found for session: {selected}")
            return
        transcript_data, loaded_path = loaded

        segments = _resolve_and_prepare_segments(transcript_data, selected)
        _render_metadata_metrics(transcript_data, segments)
        artifacts = resolve_transcript_artifacts(
            run_root=run_root,
            selected_session=session_slug,
            run_id=run_id,
        )
        render_download_row(artifacts, transcript_data, selected)

        if not segments:
            render_empty_state(
                "no_results_yet",
                "No segments in this transcript",
                "The transcript file may be empty or in an unexpected format.",
                primary_action=("Open Library", "Library"),
                secondary_action=None,
            )
            return

        # Preserve existing behavior: nav_request is consumed only once transcript
        # segments are successfully resolved and render path can continue.
        nav_state = consume_nav_request(st.session_state)
        if nav_state.clear_nav_request:
            st.session_state[NAV_REQUEST_KEY] = None
        if nav_state.jump_index is not None:
            from transcriptx.web.transcript_viewer.chapters import (
                TRANSCRIPT_SCROLL_TO_JUMP_KEY,
            )

            st.session_state[TRANSCRIPT_SCROLL_TO_JUMP_KEY] = True

        canonical_path = _resolve_canonical_transcript_path(
            loaded_path, artifacts.json_file
        )
        playback_availability = _setup_playback_availability(canonical_path)
        path_str: str | None = None
        size = 0
        mtime_ns = 0
        if canonical_path is not None:
            try:
                path_str, size, mtime_ns = transcript_revision_identity(canonical_path)
            except (FileNotFoundError, OSError):
                logger.warning(
                    "Transcript disappeared before revision identity path=%s",
                    canonical_path,
                    exc_info=True,
                )
                path_str, size, mtime_ns = None, 0, 0
                playback_availability = PlaybackAvailability(
                    enabled=False,
                    audio_path=None,
                    reason=PlaybackUnavailableReason.transcript_unresolved,
                )

        _transcript_interaction_fragment(
            segments,
            highlight_query=nav_state.highlight_query,
            jump_index=nav_state.jump_index,
            session_slug=session_slug,
            run_id=run_id,
            transcript_path=path_str,
            transcript_size=size,
            transcript_mtime_ns=mtime_ns,
            playback_availability=playback_availability,
            run_root=run_root,
        )
    except Exception as exc:
        logger.error(f"Error loading transcript: {exc}", exc_info=True)
        st.error(f"Error loading transcript: {exc}")
        st.exception(exc)
