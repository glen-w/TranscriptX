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
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import streamlit as st

from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.services.speaker_studio.segment_index import SegmentInfo

# Number of clips to pre-warm on initial panel load / after a click.
_WARM_WINDOW = 3


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _set_play_idx(play_key: str, idx: int) -> None:
    """on_click callback: set play state before the natural fragment rerun."""
    st.session_state[play_key] = idx


def _trigger_warm(
    controller: SpeakerStudioController,
    transcript_path: str,
    audio_path: Path,
    all_segs: List[SegmentInfo],
    play_seg_idx: Optional[int],
    active_id: str,
    play_key: str,
) -> None:
    """
    Enqueue background clip pre-warming for the likely next-played segments.

    Warm window:
      - If nothing is playing: first _WARM_WINDOW segments.
      - If a segment is playing: that segment + next (_WARM_WINDOW - 1) segments.

    Uses a session-state signature scoped to play_key (not a global key) to
    prevent cross-talk between pages in a multipage app.  Only enqueues when the
    visible window changes.
    """
    warm_start = play_seg_idx if play_seg_idx is not None else 0
    warm_targets = all_segs[warm_start : warm_start + _WARM_WINDOW]
    if not warm_targets:
        return

    warm_sig_key = f"{play_key}_warm_sig"
    window_sig = (
        active_id,
        tuple((round(s.start, 3), round(s.end, 3)) for s in warm_targets),
        str(audio_path),
    )
    if st.session_state.get(warm_sig_key) == window_sig:
        return
    st.session_state[warm_sig_key] = window_sig
    try:
        controller.warm_clips(
            transcript_path, [(s.start, s.end) for s in warm_targets]
        )
    except Exception:
        pass  # warming is best-effort; never propagate failures to UI


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
    all_segs:
        Pre-computed segment list for the current view.  Do not do heavy
        computation inside this fragment — pass results in from the parent.
    active_id:
        Current speaker/group identifier used to namespace widget keys.
    play_key:
        Session state key holding the currently-playing segment index (int|None).
    lines_key:
        Session state key holding the lines_shown count (int).
    max_lines:
        Default number of lines per page (used when lines_key is unset).
    autoplay:
        Whether st.audio should autoplay on load.
    include_segment_rows:
        If True (default), renders segment rows with play buttons.
        Set False for pages that render their own custom rows (e.g. speaker_studio
        with additional assign widgets); the fragment then manages only the audio
        player and warm trigger.
    """
    # ── ffmpeg / audio guard ───────────────────────────────────────────────────
    if not audio_path or not controller.ffmpeg_available():
        st.caption("_Playback unavailable — audio file or ffmpeg not found._")
        if include_segment_rows:
            lines_shown: int = st.session_state.get(lines_key, max_lines)
            for seg in all_segs[:lines_shown]:
                col_time, col_text = st.columns([1, 5])
                with col_time:
                    st.caption(f"{_fmt_time(seg.start)} – {_fmt_time(seg.end)}")
                with col_text:
                    st.write(seg.text or "_(empty)_")
        return

    play_seg_idx: Optional[int] = st.session_state.get(play_key)
    lines_shown = st.session_state.get(lines_key, max_lines)
    visible_segs = all_segs[:lines_shown]

    # ── pre-warm trigger ───────────────────────────────────────────────────────
    # Runs before the audio player so warm jobs start as early as possible.
    _trigger_warm(
        controller,
        transcript_path,
        audio_path,
        all_segs,
        play_seg_idx,
        active_id,
        play_key,
    )

    # ── audio player ───────────────────────────────────────────────────────────
    if play_seg_idx is not None:
        seg_to_play = (
            all_segs[play_seg_idx] if play_seg_idx < len(all_segs) else None
        )
        if seg_to_play:
            try:
                clip_bytes = controller.get_clip_bytes(
                    transcript_path,
                    seg_to_play.start,
                    seg_to_play.end,
                    format="mp3",
                )
                st.audio(clip_bytes, format="audio/mpeg", autoplay=autoplay)
            except Exception as e:
                st.warning(f"Could not load clip: {e}")

    if not include_segment_rows:
        return

    # ── segment rows ───────────────────────────────────────────────────────────
    # All widget keys are namespaced by active_id + index to prevent key
    # collisions and state drift across speaker changes.
    for i, seg in enumerate(visible_segs):
        col_time, col_text, col_play = st.columns([1, 5, 0.5])
        with col_time:
            st.caption(f"{_fmt_time(seg.start)} – {_fmt_time(seg.end)}")
        with col_text:
            st.write(seg.text or "_(empty)_")
        with col_play:
            # on_click sets state before the natural fragment rerun —
            # no explicit st.rerun() needed.
            st.button(
                "▶",
                key=f"play_{active_id}_{i}",
                help="Play this clip",
                on_click=_set_play_idx,
                args=(play_key, i),
            )

    # ── show more lines ────────────────────────────────────────────────────────
    if lines_shown < len(all_segs):
        remaining = len(all_segs) - lines_shown
        n_more = min(max_lines, remaining)
        if st.button(
            f"Show {n_more} more lines",
            key=f"more_lines_{active_id}",
        ):
            # Button click triggers a natural fragment rerun; state is read on
            # that rerun to show additional lines.
            st.session_state[lines_key] = lines_shown + max_lines
