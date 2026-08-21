"""
Rename Transcript page — preview content clips, then rename the managed transcript.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import streamlit as st

from transcriptx.services.speaker_studio.segment_index import SegmentInfo
from transcriptx.web.cache_helpers import cached_transcript_paths_for_speaker_views
from transcriptx.web.components.page_shell import render_page_shell
from transcriptx.web.components.playback_panel import (
    render_exact_segment_preview,
    resolve_playback_context,
)
from transcriptx.web.components.rename_form import (
    bind_suggested_rename_name,
    clear_rename_form_session_keys,
    render_transcript_rename_form,
)
from transcriptx.web.navigation import make_session_path_resolver
from transcriptx.web.services.rename_preview_clips import (
    mapped_speaker_summary_labels,
    select_rename_preview_segments,
)
from transcriptx.web.services.rename_service import RenameResult
from transcriptx.web.services.subject_service import SubjectService
from transcriptx.web.services.transcript_context_resolver import paths_match
from transcriptx.web.speaker_studio_runtime import get_shared_speaker_studio_controller
from transcriptx.web.state import (
    SELECTBOX_PLACEHOLDER_TRANSCRIPT,
    WORKFLOW_NAV_TRANSCRIPT_PATH,
)

_FORM_KEY = "rename_transcript_page_form"
_PICKER_KEY = "rename_transcript_select"
_SELECTED_PATH_KEY = "rename_transcript_selected_path"
_PREVIEW_LIMIT = 10


def _transcript_ns(transcript_path: str | Path) -> str:
    try:
        resolved = str(Path(transcript_path).resolve())
    except OSError:
        resolved = str(transcript_path)
    return hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:12]


def rename_play_key(transcript_path: str | Path) -> str:
    return f"rename:{_transcript_ns(transcript_path)}:play_seg"


def clear_rename_page_path_keys(transcript_path: str | Path | None) -> None:
    """Clear Rename-page session keys scoped to a transcript path."""
    if not transcript_path:
        return
    play = rename_play_key(transcript_path)
    st.session_state[play] = None
    st.session_state[f"{play}_warm_sig"] = None
    st.session_state.pop(f"{play}_warm_pending", None)
    from transcriptx.web.components.playback_panel import _audio_resolve_cache_key

    st.session_state.pop(_audio_resolve_cache_key(str(transcript_path)), None)


def apply_rename_page_post_rename(result: RenameResult) -> None:
    """Replace old-path page state with the renamed transcript."""
    old_t = result.old_transcript_path
    new_t = result.new_transcript_path
    clear_rename_form_session_keys(_FORM_KEY)
    clear_rename_page_path_keys(old_t)
    st.session_state.pop(WORKFLOW_NAV_TRANSCRIPT_PATH, None)
    st.session_state.pop(_PICKER_KEY, None)
    if new_t:
        st.session_state[_SELECTED_PATH_KEY] = str(new_t)
        SubjectService.set_transcript_context_from_path(
            st.session_state,
            new_t,
            session_resolver=make_session_path_resolver(),
        )
        bind_suggested_rename_name(new_t, form_key=_FORM_KEY, date_prefix_prefill=True)
    else:
        st.session_state.pop(_SELECTED_PATH_KEY, None)


def _path_is_file(path: str | Path | None) -> bool:
    if not path:
        return False
    try:
        return Path(path).is_file()
    except OSError:
        return False


def _consume_one_shot_nav() -> str | None:
    raw = st.session_state.pop(WORKFLOW_NAV_TRANSCRIPT_PATH, None)
    if raw and _path_is_file(raw):
        return str(raw)
    return None


def _valid_context_transcript() -> str | None:
    current = SubjectService.current_transcript_path(st.session_state)
    if current and _path_is_file(current):
        return str(current)
    selected = st.session_state.get(_SELECTED_PATH_KEY)
    if selected and _path_is_file(selected):
        return str(selected)
    return None


def _paths_with_preferred(paths: list[Path], preferred: str | None) -> list[Path]:
    if not preferred:
        return list(paths)
    preferred_path = Path(preferred)
    if not _path_is_file(preferred_path):
        return list(paths)
    if any(paths_match(p, preferred_path) for p in paths):
        return list(paths)
    return sorted([*paths, preferred_path], key=lambda p: str(p.resolve()))


def _bind_picker_index(options: list[Path], default_idx: int) -> None:
    n = len(options)
    if _PICKER_KEY in st.session_state:
        current = st.session_state.get(_PICKER_KEY)
        if not isinstance(current, int) or current < 0 or current > n:
            st.session_state[_PICKER_KEY] = default_idx if 0 <= default_idx <= n else 0
            return
        if current == 0 and default_idx > 0:
            st.session_state[_PICKER_KEY] = default_idx
        return
    if 0 <= default_idx <= n:
        st.session_state[_PICKER_KEY] = default_idx


def _default_picker_index(options: list[Path], preferred: str | None) -> int:
    """1-based index into options, or 0 for placeholder."""
    if preferred:
        for i, opt in enumerate(options):
            if paths_match(opt, preferred):
                return i + 1
    ctx_idx = SubjectService.index_in_path_options(st.session_state, options)
    if ctx_idx > 0:
        return ctx_idx
    if options:
        return 1
    return 0


def _load_segments(path: Path) -> tuple[list[SegmentInfo] | None, str | None]:
    controller = get_shared_speaker_studio_controller()
    try:
        segments = controller.list_segments(str(path))
    except Exception as exc:
        return None, f"Could not read transcript segments: {exc}"
    return list(segments or []), None


def _render_preview(path: Path, segments: list[SegmentInfo]) -> None:
    preview = select_rename_preview_segments(segments, limit=_PREVIEW_LIMIT)
    mapped = mapped_speaker_summary_labels(preview)
    if mapped:
        st.caption("Named speakers in preview: " + ", ".join(mapped))
    elif any((s.speaker_diarized_id or s.speaker) for s in preview):
        st.caption("Speakers are not named yet — showing diarized IDs.")

    if not preview:
        st.info(
            "No valid timed segments with text were found for a content preview. "
            "You can still rename the transcript below."
        )
        return

    st.markdown(f"#### Content preview ({len(preview)} clips)")
    controller = get_shared_speaker_studio_controller()
    playback_ctx = resolve_playback_context(controller, str(path))
    render_exact_segment_preview(
        controller,
        str(path),
        preview,
        play_key=rename_play_key(path),
        active_id="rename_preview",
        show_speaker_labels=True,
        playback_context=playback_ctx,
    )


def render_rename_transcript_page() -> None:
    """Render the self-contained Rename Transcript workflow page."""
    render_page_shell(
        "Rename Transcript",
        "Review sample clips from the recording, then choose a new file name. "
        "Suggested names are date-prefixed (YYMMDD_) when a date can be resolved.",
    )

    # Peek preferred path before consuming one-shot nav (for discovery lag).
    peek_nav = st.session_state.get(WORKFLOW_NAV_TRANSCRIPT_PATH)
    paths = list(cached_transcript_paths_for_speaker_views() or [])
    preferred_for_list = (
        peek_nav
        or st.session_state.get(_SELECTED_PATH_KEY)
        or SubjectService.current_transcript_path(st.session_state)
    )
    paths = _paths_with_preferred(
        paths, str(preferred_for_list) if preferred_for_list else None
    )

    if not paths:
        st.info("No transcripts found. Import or transcribe a recording first.")
        return

    from transcriptx.web.transcript_option_format import decorate_transcript_picker_label

    options = list(paths)
    labels = [
        decorate_transcript_picker_label(p.stem or str(p), path=p) for p in options
    ]

    # Precedence: one-shot nav → valid current context → picker → first available.
    one_shot = _consume_one_shot_nav()
    preferred = one_shot or _valid_context_transcript()
    default_idx = _default_picker_index(options, preferred)
    _bind_picker_index(options, default_idx)

    idx = st.selectbox(
        "Transcript",
        range(len(options) + 1),
        format_func=lambda i: (
            SELECTBOX_PLACEHOLDER_TRANSCRIPT if i == 0 else labels[i - 1]
        ),
        key=_PICKER_KEY,
    )
    if not isinstance(idx, int) or idx <= 0:
        st.session_state.pop(_SELECTED_PATH_KEY, None)
        st.info("Select a transcript to rename.")
        return

    active = options[idx - 1]
    prev_selected = st.session_state.get(_SELECTED_PATH_KEY)
    if prev_selected and not paths_match(prev_selected, active):
        clear_rename_form_session_keys(_FORM_KEY)
        clear_rename_page_path_keys(prev_selected)
    st.session_state[_SELECTED_PATH_KEY] = str(active)

    if not _path_is_file(active):
        st.warning("Selected transcript is missing or unreadable.")
        st.session_state.pop(_SELECTED_PATH_KEY, None)
        return

    SubjectService.set_transcript_context_from_path(
        st.session_state,
        active,
        session_resolver=make_session_path_resolver(),
    )

    segments, load_error = _load_segments(active)
    if load_error:
        st.warning(load_error)
    elif segments is not None:
        _render_preview(active, segments)

    light_meta = None
    try:
        from transcriptx.web.cache_helpers import get_cached_light_transcript_metadata

        light_meta = get_cached_light_transcript_metadata()
    except Exception:
        light_meta = None

    render_transcript_rename_form(
        active,
        form_key=_FORM_KEY,
        title="Rename transcript",
        as_subheader=True,
        library_transcripts=light_meta,
        on_success=apply_rename_page_post_rename,
        date_prefix_prefill=True,
    )
