"""
Shared playback panel component for speaker identification pages.

``render_playback_panel`` is decorated with ``@st.fragment`` so play-button
clicks can rerun only this region when the decorated entry is used as a
**sibling** surface. Speaker Identification embeds undecorated
``render_playback_panel_body`` inside ``_speaker_id_workspace_fragment`` (no
nested fragments), so play clicks there rerun the larger workspace fragment;
isolation comes from callbacks, caching, and avoiding heavy voice work on the
playback hot path—not from a nested playback fragment.

Fragment rerun semantics (decorated entry):
  Widget interactions inside the fragment naturally trigger a fragment-scoped
  rerun.  Do NOT call st.rerun() for play events; the on_click callback sets
  session state and the fragment rerenders automatically.  Only call
  st.rerun(scope="fragment") if a manual fragment rerun is truly needed for
  some other reason.  Plain st.rerun() defaults to scope="app" and causes a
  full-page rerun, defeating the purpose of the fragment.

Cold foreground generation remains synchronous by design: if a pre-warm job
has not finished yet, get_clip_bytes() blocks until ffmpeg completes.

Cache is disk-backed and cross-session/process-agnostic.  Session state
controls only UI behaviour and warm triggers, not clip ownership.

Architecture invariant: ``render_playback_panel`` is the only ``@st.fragment``
in this module. Shared helpers below must remain undecorated so callers that
already run inside a fragment (e.g. Transcript, Speaker ID workspace) never
nest fragments. Prefer ``render_playback_panel_body`` from an outer fragment.

``audio_path`` / ``PlaybackContext`` are resolved for UI gating and warm
signatures. Prefer passing ``playback_context`` so callers do not re-resolve
audio or FFmpeg on every play click. Clip extraction still validates file
existence/stat before ffmpeg.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional, Sequence

import streamlit as st

from transcriptx.core.utils.logger import get_logger
from transcriptx.services.speaker_studio.clip_service import WarmClipsResult
from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.services.speaker_studio.segment_index import SegmentInfo

logger = get_logger()

# Number of clips to pre-warm when visible_count is not provided
_WARM_WINDOW = 3
# Session cache of resolved audio for workspace reruns (validated each use).
_AUDIO_RESOLVE_CACHE_PREFIX = "_tx_playback_audio_resolve:"


@dataclass(frozen=True)
class PlaybackContext:
    """Resolved playback prerequisites for one render (do not cache missing audio)."""

    audio_path: Optional[Path]
    audio_fingerprint: Optional[tuple[str, int, int]]
    ffmpeg_available: bool


def _audio_resolve_cache_key(transcript_path: str) -> str:
    try:
        resolved = str(Path(transcript_path).resolve())
    except OSError:
        resolved = str(transcript_path)
    return f"{_AUDIO_RESOLVE_CACHE_PREFIX}{resolved}"


def _fingerprint_audio(path: Path) -> Optional[tuple[str, int, int]]:
    try:
        if not path.is_file():
            return None
        st_ = path.stat()
        return (
            str(path.resolve()),
            int(st_.st_size),
            int(st_.st_mtime_ns),
        )
    except OSError:
        return None


def resolve_playback_context(
    controller: SpeakerStudioController,
    transcript_path: str,
) -> PlaybackContext:
    """Resolve audio + ffmpeg; reuse session cache when path+fingerprint still valid.

    Missing audio is never sticky-cached. FFmpeg availability is read from the
    shared ClipService (process-memoized ``_find_ffmpeg``).
    """
    cache_key = _audio_resolve_cache_key(transcript_path)
    cached = st.session_state.get(cache_key)
    audio_path: Optional[Path] = None
    fingerprint: Optional[tuple[str, int, int]] = None

    if isinstance(cached, dict) and cached.get("path"):
        try:
            candidate = Path(str(cached["path"]))
            fp = _fingerprint_audio(candidate)
            if fp is not None and fp == cached.get("fingerprint"):
                audio_path = candidate
                fingerprint = fp
            else:
                st.session_state.pop(cache_key, None)
        except (TypeError, OSError):
            st.session_state.pop(cache_key, None)

    if audio_path is None:
        try:
            raw = controller.get_audio_path(transcript_path)
            if raw is not None:
                candidate = Path(raw)
                fp = _fingerprint_audio(candidate)
                if fp is not None:
                    audio_path = candidate
                    fingerprint = fp
                    st.session_state[cache_key] = {
                        "path": str(candidate),
                        "fingerprint": fp,
                    }
        except OSError:
            audio_path = None
            fingerprint = None

    return PlaybackContext(
        audio_path=audio_path,
        audio_fingerprint=fingerprint,
        ffmpeg_available=bool(controller.ffmpeg_available()),
    )


def prioritized_warm_indices(
    length: int,
    *,
    play_seg_idx: Optional[int],
    visible_count: int,
) -> list[int]:
    """Order warm targets: active/clicked, then nearby visible, then remainder."""
    if length <= 0 or visible_count <= 0:
        return []
    n = min(int(visible_count), length)
    visible = list(range(n))
    play_idx = sanitize_play_index(play_seg_idx, length)
    if play_idx is None:
        return visible
    ordered: list[int] = []
    seen: set[int] = set()

    def _add(idx: int) -> None:
        if 0 <= idx < n and idx not in seen:
            ordered.append(idx)
            seen.add(idx)

    _add(play_idx)
    for dist in range(1, n + 1):
        _add(play_idx - dist)
        _add(play_idx + dist)
    for idx in visible:
        _add(idx)
    return ordered


# Tiny silent MP3 kept mounted when no segment is selected so the first ▶ click
# updates an existing ``st.audio`` widget instead of inserting one above the
# transcript (which Streamlit scrolls into view as the "player bar").
_IDLE_CLIP_MP3 = base64.b64decode(
    "SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjYyLjEyLjEwMAAAAAAAAAAAAAAA/+M4wAAA"
    "AAAAAAAAAEluZm8AAAAPAAAAAwAAAbAAqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqq"
    "qqqqqqqq1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV1dXV////////////////"
    "////////////////////////////AAAAAExhdmM2Mi4yOAAAAAAAAAAAAAAAACQC8AAA"
    "AAAAAAGw9wpEpwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAA/+MYxAAAAANIAAAAAExBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV/+MYxDsAAANIAAAAAFVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV/+MY"
    "xHYAAANIAAAAAFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
    "VVVVVVVVVVVVVVVVVVVVVVVV"
)


class PlaybackUnavailableReason(str, Enum):
    """Stable reason codes when segment playback cannot be offered."""

    transcript_unresolved = "transcript_unresolved"
    audio_missing = "audio_missing"
    ffmpeg_missing = "ffmpeg_missing"
    controller_error = "controller_error"
    timing_unavailable = "timing_unavailable"


@dataclass(frozen=True)
class PlaybackAvailability:
    """Result of playback preflight checks."""

    enabled: bool
    audio_path: Optional[Path]
    reason: Optional[PlaybackUnavailableReason] = None


def fmt_time(seconds: float) -> str:
    """Format seconds as M:SS or H:MM:SS."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# Backward-compatible alias for callers that still import the private name.
_fmt_time = fmt_time


def set_active_clip(play_key: str, idx: int) -> None:
    """on_click callback: set play state before the natural fragment rerun."""
    st.session_state[play_key] = idx
    # One-shot follow-along scroll for Theme D reading UX.
    st.session_state[f"{play_key}_scroll_playing"] = True


def consume_scroll_playing(play_key: str, session_state: Any | None = None) -> bool:
    """Consume one-shot follow-along scroll request for the active play key."""
    state = session_state if session_state is not None else st.session_state
    key = f"{play_key}_scroll_playing"
    if not state.get(key):
        return False
    state[key] = False
    return True


# Backward-compatible alias.
_set_play_idx = set_active_clip


def _increment_lines_shown(lines_key: str, increment: int) -> None:
    """on_click callback: increase visible lines before fragment rerun."""
    current = int(st.session_state.get(lines_key, 0) or 0)
    st.session_state[lines_key] = current + increment


def sanitize_play_index(value: object, length: int) -> Optional[int]:
    """Accept only non-negative in-range integers (reject bool / negative / OOB)."""
    if type(value) is not int:
        return None
    if value < 0 or value >= length:
        return None
    return value


def sanitize_lines_shown(value: object, *, length: int, default: int) -> int:
    """Clamp lines_shown to 0..length; restore default for malformed values."""
    if type(value) is not int:
        return max(0, min(default, length))
    if value < 0:
        return max(0, min(default, length))
    return min(value, length)


def clear_playback_session_keys(play_key: str) -> None:
    """Clear active clip and warm signature for a play key."""
    st.session_state[play_key] = None
    st.session_state[f"{play_key}_warm_sig"] = None
    st.session_state.pop(f"{play_key}_scroll_playing", None)
    st.session_state.pop(f"{play_key}_warm_pending", None)


def resolve_playback_availability(
    transcript_path: Optional[str | Path],
    controller: SpeakerStudioController,
) -> PlaybackAvailability:
    """
    Check playback prerequisites in order: path → audio → ffmpeg.

    Stops after the first failure so audio/ffmpeg are not probed unnecessarily.
    Unexpected controller errors degrade to ``controller_error`` rather than
    raising into page-wide handlers.
    """
    if transcript_path is None or not str(transcript_path).strip():
        return PlaybackAvailability(
            enabled=False,
            audio_path=None,
            reason=PlaybackUnavailableReason.transcript_unresolved,
        )
    path_str = str(transcript_path)
    try:
        if not Path(path_str).is_file():
            return PlaybackAvailability(
                enabled=False,
                audio_path=None,
                reason=PlaybackUnavailableReason.transcript_unresolved,
            )
        audio_path = controller.get_audio_path(path_str)
        if not audio_path or not Path(audio_path).is_file():
            return PlaybackAvailability(
                enabled=False,
                audio_path=None,
                reason=PlaybackUnavailableReason.audio_missing,
            )
        if not controller.ffmpeg_available():
            return PlaybackAvailability(
                enabled=False,
                audio_path=Path(audio_path),
                reason=PlaybackUnavailableReason.ffmpeg_missing,
            )
        return PlaybackAvailability(
            enabled=True, audio_path=Path(audio_path), reason=None
        )
    except Exception:
        logger.warning(
            "Playback availability check failed for transcript=%s",
            path_str,
            exc_info=True,
        )
        return PlaybackAvailability(
            enabled=False,
            audio_path=None,
            reason=PlaybackUnavailableReason.controller_error,
        )


def render_playback_unavailable(
    reason: PlaybackUnavailableReason,
) -> None:
    """Render one caption block per unavailable reason (tips included)."""
    if reason == PlaybackUnavailableReason.audio_missing:
        st.caption(
            "_Playback unavailable — audio file not found. "
            "Tip: verify the transcript's source recording exists under mounted recordings._"
        )
        return
    if reason == PlaybackUnavailableReason.ffmpeg_missing:
        st.caption(
            "_Playback unavailable — ffmpeg not found. "
            "Tip: install ffmpeg or ensure it is on PATH inside runtime._"
        )
        return
    if reason == PlaybackUnavailableReason.transcript_unresolved:
        st.caption("_Playback unavailable — transcript path could not be resolved._")
        return
    if reason == PlaybackUnavailableReason.timing_unavailable:
        st.caption("_Playback unavailable — visible segments lack valid timing data._")
        return
    st.caption("_Playback unavailable — audio playback could not be initialised._")


def trigger_clip_warm(
    controller: SpeakerStudioController,
    transcript_path: str,
    audio_path: Path,
    ordered_segs: Sequence[SegmentInfo],
    play_seg_idx: Optional[int],
    active_id: str,
    play_key: str,
    *,
    visible_count: Optional[int] = None,
    playback_context: Optional[PlaybackContext] = None,
) -> Optional[WarmClipsResult]:
    """
    Enqueue background clip pre-warming with priority + pending queue.

    Order: active/clicked clip, nearby visible clips, then remaining visible.
    When ClipService hits in-flight backpressure, remaining targets stay in a
    session pending queue and are retried on later renders so all visible clips
    eventually warm. Synchronous ``get_clip_bytes`` remains the correctness
    fallback for an uncached click.
    """
    if not ordered_segs:
        return None

    target_count = (
        _WARM_WINDOW if visible_count is None else max(0, int(visible_count))
    )
    target_count = min(target_count, len(ordered_segs))
    if target_count <= 0:
        return None

    indices = prioritized_warm_indices(
        len(ordered_segs),
        play_seg_idx=play_seg_idx,
        visible_count=target_count,
    )
    warm_targets = [ordered_segs[i] for i in indices]
    if not warm_targets:
        return None

    try:
        audio = Path(audio_path)
        if not audio.is_file():
            return None
        if (
            playback_context is not None
            and playback_context.audio_fingerprint is not None
        ):
            audio_revision = playback_context.audio_fingerprint
        else:
            audio_stat = audio.stat()
            audio_revision = (
                str(audio.resolve()),
                int(audio_stat.st_size),
                int(audio_stat.st_mtime_ns),
            )
    except OSError:
        return None

    pending_key = f"{play_key}_warm_pending"
    warm_sig_key = f"{play_key}_warm_sig"
    window_sig = (
        active_id,
        tuple((round(s.start, 3), round(s.end, 3)) for s in warm_targets),
        audio_revision,
    )
    if st.session_state.get(warm_sig_key) == window_sig:
        st.session_state.pop(pending_key, None)
        return None

    # Merge prior pending pairs (bounded) ahead of the current priority list.
    pending_raw = st.session_state.get(pending_key)
    pending_pairs: list[tuple[float, float]] = []
    if isinstance(pending_raw, (list, tuple)):
        for item in pending_raw:
            if (
                isinstance(item, (list, tuple))
                and len(item) == 2
                and isinstance(item[0], (int, float))
                and isinstance(item[1], (int, float))
            ):
                pending_pairs.append((float(item[0]), float(item[1])))

    desired_pairs = [(float(s.start), float(s.end)) for s in warm_targets]
    seen_pairs: set[tuple[float, float]] = set()
    merged: list[tuple[float, float]] = []
    for pair in [*desired_pairs, *pending_pairs]:
        key = (round(pair[0], 3), round(pair[1], 3))
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        merged.append(pair)
    # Cap pending merge so a huge backlog cannot grow without bound.
    merged = merged[: max(target_count * 2, target_count)]

    try:
        result = controller.warm_clips(
            transcript_path,
            merged,
            audio_path=audio,
        )
    except Exception:
        logger.warning(
            "Clip warm enqueue failed for transcript=%s play_key=%s",
            transcript_path,
            play_key,
            exc_info=True,
        )
        return None

    if not isinstance(result, WarmClipsResult):
        return None

    if result.fully_accepted:
        st.session_state[warm_sig_key] = window_sig
        st.session_state.pop(pending_key, None)
    else:
        # Keep the full desired window pending so later renders drain it.
        st.session_state[pending_key] = desired_pairs
        st.session_state.pop(warm_sig_key, None)
    return result


# Backward-compatible alias.
_trigger_warm = trigger_clip_warm


def _sanitised_clip_warning() -> str:
    return (
        "Could not load clip. The recording may be unavailable "
        "or the segment could not be extracted."
    )


def render_active_clip(
    controller: SpeakerStudioController,
    transcript_path: str,
    segment: Optional[SegmentInfo],
    *,
    autoplay: bool = False,
    playback_context: Optional[PlaybackContext] = None,
) -> None:
    """
    Render ``st.audio`` for one segment, or a sanitised warning on failure.

    When ``segment`` is None, mounts a silent idle clip so the player widget
    stays in the layout. First-play must not insert a new audio block above
    the transcript (Streamlit scrolls that into view).

    Failures are caught locally so surrounding transcript UI stays usable and
    another segment can be selected without clearing the fragment.
    """
    if segment is None:
        st.audio(_IDLE_CLIP_MP3, format="audio/mpeg", autoplay=False)
        return
    try:
        resolved_audio = (
            playback_context.audio_path if playback_context is not None else None
        )
        clip_bytes = controller.get_clip_bytes(
            transcript_path,
            segment.start,
            segment.end,
            format="mp3",
            audio_path=resolved_audio,
        )
        st.audio(clip_bytes, format="audio/mpeg", autoplay=autoplay)
    except Exception:
        logger.warning(
            "Clip generation failed transcript=%s segment_index=%s start=%s end=%s",
            transcript_path,
            segment.index,
            segment.start,
            segment.end,
            exc_info=True,
        )
        st.warning(_sanitised_clip_warning())


def _render_fallback_segment_rows(
    all_segs: List[SegmentInfo],
    lines_shown: int,
) -> None:
    for seg in all_segs[:lines_shown]:
        col_time, col_text = st.columns([1, 5])
        with col_time:
            st.caption(f"{fmt_time(seg.start)} – {fmt_time(seg.end)}")
        with col_text:
            st.write(seg.text or "_(empty)_")


def render_playback_panel_body(
    controller: SpeakerStudioController,
    transcript_path: str,
    audio_path: Optional[Path],
    all_segs: List[SegmentInfo],
    active_id: str,
    play_key: str,
    lines_key: str,
    max_lines: int,
    autoplay: bool = False,
    include_segment_rows: bool = True,
    playback_context: Optional[PlaybackContext] = None,
) -> None:
    """
    Undecorated playback panel body for use inside an outer ``@st.fragment``.

    Same parameters and behaviour as ``render_playback_panel``. Callers that are
    not already inside a fragment should use ``render_playback_panel`` instead.
    """
    ctx = playback_context
    effective_audio = (
        ctx.audio_path if ctx is not None else audio_path
    )
    ffmpeg_ok = (
        ctx.ffmpeg_available if ctx is not None else controller.ffmpeg_available()
    )

    # ── ffmpeg / audio guard ───────────────────────────────────────────────────
    if not effective_audio or not Path(effective_audio).is_file():
        clear_playback_session_keys(play_key)
        render_playback_unavailable(PlaybackUnavailableReason.audio_missing)
        if include_segment_rows:
            lines_shown = sanitize_lines_shown(
                st.session_state.get(lines_key, max_lines),
                length=len(all_segs),
                default=max_lines,
            )
            _render_fallback_segment_rows(all_segs, lines_shown)
        return

    if not ffmpeg_ok:
        clear_playback_session_keys(play_key)
        render_playback_unavailable(PlaybackUnavailableReason.ffmpeg_missing)
        if include_segment_rows:
            lines_shown = sanitize_lines_shown(
                st.session_state.get(lines_key, max_lines),
                length=len(all_segs),
                default=max_lines,
            )
            _render_fallback_segment_rows(all_segs, lines_shown)
        return

    play_seg_idx = sanitize_play_index(st.session_state.get(play_key), len(all_segs))
    if st.session_state.get(play_key) is not None and play_seg_idx is None:
        st.session_state[play_key] = None
    lines_shown = sanitize_lines_shown(
        st.session_state.get(lines_key, max_lines),
        length=len(all_segs),
        default=max_lines,
    )
    st.session_state[lines_key] = lines_shown
    visible_segs = all_segs[:lines_shown]

    # ── pre-warm trigger ───────────────────────────────────────────────────────
    # Warm all currently visible lines; ClipService applies bounded backpressure.
    trigger_clip_warm(
        controller,
        transcript_path,
        Path(effective_audio),
        all_segs,
        play_seg_idx,
        active_id,
        play_key,
        visible_count=lines_shown,
        playback_context=ctx,
    )

    # ── audio player (always mounted when playback is available) ───────────────
    seg_to_play = all_segs[play_seg_idx] if play_seg_idx is not None else None
    render_active_clip(
        controller,
        transcript_path,
        seg_to_play,
        autoplay=autoplay,
        playback_context=ctx,
    )

    if not include_segment_rows:
        return

    # ── segment rows ───────────────────────────────────────────────────────────
    for i, seg in enumerate(visible_segs):
        col_time, col_text, col_play = st.columns([1, 5, 0.5])
        with col_time:
            st.caption(f"{fmt_time(seg.start)} – {fmt_time(seg.end)}")
        with col_text:
            st.write(seg.text or "_(empty)_")
        with col_play:
            st.button(
                "▶",
                key=f"{play_key}_btn_{active_id}_{i}",
                help="Play this clip",
                on_click=set_active_clip,
                args=(play_key, i),
            )

    if lines_shown < len(all_segs):
        remaining = len(all_segs) - lines_shown
        n_more = min(max_lines, remaining)
        st.button(
            f"Show {n_more} more lines",
            key=f"{lines_key}_more_{active_id}",
            on_click=_increment_lines_shown,
            args=(lines_key, n_more),
        )


@st.fragment
def render_playback_panel(
    controller: SpeakerStudioController,
    transcript_path: str,
    audio_path: Optional[Path],
    all_segs: List[SegmentInfo],
    active_id: str,
    play_key: str,
    lines_key: str,
    max_lines: int,
    autoplay: bool = False,
    include_segment_rows: bool = True,
    playback_context: Optional[PlaybackContext] = None,
) -> None:
    """
    Fragment-scoped playback panel.

    Parameters
    ----------
    controller:
        SpeakerStudioController instance (passed in; no data work done here).
    transcript_path:
        Path string for the active transcript.
    audio_path:
        Resolved audio file path, or None if not found.
        Used for UI gating and warm signatures only when playback_context omitted.
    all_segs:
        Pre-computed segment list for the current view.  Do not do heavy
        computation inside this fragment — pass results in from the parent.
    active_id:
        Current speaker/group identifier used to namespace widget keys.
    play_key:
        Session state key holding the currently-playing segment list index (int|None).
    lines_key:
        Session state key holding the lines_shown count (int).
    max_lines:
        Default number of lines per page (used when lines_key is unset).
    autoplay:
        Whether st.audio should autoplay on load.
    include_segment_rows:
        If True (default), renders segment rows with play buttons.
        Set False for pages that render their own custom rows (e.g. Speaker ID
        with additional assign widgets); the fragment then manages only the audio
        player and warm trigger.
    playback_context:
        Optional pre-resolved audio/ffmpeg context for the current render.
    """
    render_playback_panel_body(
        controller,
        transcript_path,
        audio_path,
        all_segs,
        active_id,
        play_key,
        lines_key,
        max_lines,
        autoplay=autoplay,
        include_segment_rows=include_segment_rows,
        playback_context=playback_context,
    )
