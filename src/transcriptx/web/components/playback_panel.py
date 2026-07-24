"""
Shared playback panel component for speaker identification pages.

Decorated with @st.fragment so only this region reruns on play-button clicks —
the rest of the page (header, metrics, name assignment, navigation) does not dim
or re-execute.

Fragment rerun semantics:
  Widget interactions inside the fragment naturally trigger a fragment-scoped
  rerun.  Do NOT call st.rerun() for play events; the on_click callback sets
  session state and the fragment rerenders automatically.  Only call
  st.rerun(scope="fragment") if a manual fragment rerun is truly needed for
  some other reason.  Plain st.rerun() defaults to scope="app" and causes a
  full-page rerun, defeating the purpose of the fragment.

Cold foreground generation remains synchronous by design: if a pre-warm job
has not finished yet, get_clip_bytes() blocks until ffmpeg completes.  This is
now isolated to the playback fragment rather than the full page — the rest of
the UI stays interactive.

Cache is disk-backed and cross-session/process-agnostic.  Session state
controls only UI behaviour and warm triggers, not clip ownership.

Architecture invariant: ``render_playback_panel`` is the only ``@st.fragment``
in this module. Shared helpers below must remain undecorated so callers that
already run inside a fragment (e.g. Transcript) never nest fragments.

``audio_path`` is resolved once for UI gating and warm signatures only.
``get_clip_bytes`` re-resolves audio through the controller, so extraction must
tolerate the recording disappearing or changing after preflight.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Sequence

import streamlit as st

from transcriptx.core.utils.logger import get_logger
from transcriptx.services.speaker_studio.clip_service import WarmClipsResult
from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.services.speaker_studio.segment_index import SegmentInfo

logger = get_logger()

# Number of clips to pre-warm on initial panel load / after a click.
_WARM_WINDOW = 3

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
) -> None:
    """
    Enqueue background clip pre-warming for the likely next-played segments.

    Warm window:
      - If nothing is playing: first _WARM_WINDOW segments.
      - If a segment is playing: that list position + next (_WARM_WINDOW - 1).

    ``play_seg_idx`` is a position into ``ordered_segs`` (not a source index).
    Callers that key state by source index must resolve the list position first.

    The warm signature is stored only when every target in the window was
    accepted (enqueued, already cached, or already in flight). Transient
    unavailability, backpressure, and closed executors leave the signature
    unset so the next render can retry. The signature includes audio path
    revision (size + mtime_ns) so replaced recordings invalidate warming.
    """
    if not ordered_segs:
        return

    warm_start = 0
    play_idx = sanitize_play_index(play_seg_idx, len(ordered_segs))
    if play_idx is not None:
        warm_start = play_idx
    warm_targets = list(ordered_segs[warm_start : warm_start + _WARM_WINDOW])
    if not warm_targets:
        return

    try:
        audio = Path(audio_path)
        if not audio.is_file():
            return
        audio_stat = audio.stat()
        audio_revision = (
            str(audio.resolve()),
            int(audio_stat.st_size),
            int(audio_stat.st_mtime_ns),
        )
    except OSError:
        return

    warm_sig_key = f"{play_key}_warm_sig"
    window_sig = (
        active_id,
        tuple((round(s.start, 3), round(s.end, 3)) for s in warm_targets),
        audio_revision,
    )
    if st.session_state.get(warm_sig_key) == window_sig:
        return
    try:
        result = controller.warm_clips(
            transcript_path, [(s.start, s.end) for s in warm_targets]
        )
    except Exception:
        logger.warning(
            "Clip warm enqueue failed for transcript=%s play_key=%s",
            transcript_path,
            play_key,
            exc_info=True,
        )
        return
    if isinstance(result, WarmClipsResult) and result.fully_accepted:
        st.session_state[warm_sig_key] = window_sig


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
        clip_bytes = controller.get_clip_bytes(
            transcript_path,
            segment.start,
            segment.end,
            format="mp3",
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
        Used for UI gating and warm signatures only; clip extraction re-resolves.
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
    """
    # ── ffmpeg / audio guard ───────────────────────────────────────────────────
    if not audio_path or not Path(audio_path).is_file():
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

    if not controller.ffmpeg_available():
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
    # Runs before the audio player so warm jobs start as early as possible.
    trigger_clip_warm(
        controller,
        transcript_path,
        audio_path,
        all_segs,
        play_seg_idx,
        active_id,
        play_key,
    )

    # ── audio player (always mounted when playback is available) ───────────────
    seg_to_play = all_segs[play_seg_idx] if play_seg_idx is not None else None
    render_active_clip(
        controller,
        transcript_path,
        seg_to_play,
        autoplay=autoplay,
    )

    if not include_segment_rows:
        return

    # ── segment rows ───────────────────────────────────────────────────────────
    # All widget keys are namespaced by active_id + index to prevent key
    # collisions and state drift across speaker changes.
    for i, seg in enumerate(visible_segs):
        col_time, col_text, col_play = st.columns([1, 5, 0.5])
        with col_time:
            st.caption(f"{fmt_time(seg.start)} – {fmt_time(seg.end)}")
        with col_text:
            st.write(seg.text or "_(empty)_")
        with col_play:
            # on_click sets state before the natural fragment rerun —
            # no explicit st.rerun() needed.
            st.button(
                "▶",
                key=f"play_{active_id}_{i}",
                help="Play this clip",
                on_click=set_active_clip,
                args=(play_key, i),
            )

    # ── show more lines ────────────────────────────────────────────────────────
    if lines_shown < len(all_segs):
        remaining = len(all_segs) - lines_shown
        n_more = min(max_lines, remaining)
        st.button(
            f"Show {n_more} more lines",
            key=f"more_lines_{active_id}",
            # on_click sets state before rerun so the first click renders more.
            on_click=_increment_lines_shown,
            args=(lines_key, n_more),
        )
