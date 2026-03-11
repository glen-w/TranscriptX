"""
Speaker Identification page — interactive speaker-by-speaker naming.

Mirrors the CLI flow: groups segments by diarized speaker ID, shows sample
lines for the active speaker, supports audio clip playback (if audio is
available), and lets the user assign a name or mark as ignored before
moving to the next speaker.

The audio player + segment rows are rendered via render_playback_panel()
(@st.fragment), so play-button clicks rerun only that region — the rest of
the page (header, metrics, name assignment, navigation) does not dim.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

import streamlit as st

from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.services.speaker_studio.segment_index import SegmentInfo
from transcriptx.web.components.playback_panel import _fmt_time, render_playback_panel
from transcriptx.web.page_modules.speaker_studio import (
    _transcript_paths_for_speaker_views,
)
from transcriptx.web.state import SELECTED_TRANSCRIPT_PATH

# How many sample lines to show per speaker by default
_LINES_PER_PAGE = 8


# ── helpers ──────────────────────────────────────────────────────────────────


def _group_by_diarized_id(
    segments: List[SegmentInfo],
) -> Dict[str, List[SegmentInfo]]:
    """Return ordered dict: diarized_id → list of SegmentInfo."""
    groups: Dict[str, List[SegmentInfo]] = defaultdict(list)
    seen_order: List[str] = []
    for seg in segments:
        did = seg.speaker_diarized_id or seg.speaker
        if did and did not in groups:
            seen_order.append(did)
        if did:
            groups[did].append(seg)
    return {k: groups[k] for k in seen_order}


# ── main render ──────────────────────────────────────────────────────────────


def render_speaker_id_page() -> None:
    """Render the speaker-by-speaker identification page."""
    st.markdown(
        '<div class="main-header">🗣️ Speaker Identification</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Work through each speaker one at a time: review their lines, "
        "play a clip, then assign a name or mark as ignored."
    )

    controller = SpeakerStudioController()
    paths = _transcript_paths_for_speaker_views()
    if paths:
        transcripts = controller.list_transcripts_from_paths(paths)
    else:
        transcripts = []
    if not transcripts:
        try:
            transcripts = controller.list_transcripts(canonical_only=False)
        except TypeError:
            transcripts = controller.list_transcripts()
    if not transcripts:
        st.info("No transcripts found. Add transcript JSON files first.")
        return

    # ── transcript picker ────────────────────────────────────────────────────
    selected_path = st.session_state.get(SELECTED_TRANSCRIPT_PATH)
    options = [t.path for t in transcripts]
    labels = [
        f"{t.base_name} ({t.speaker_map_status}, {t.segment_count} segs)"
        for t in transcripts
    ]
    default_idx = options.index(selected_path) if selected_path in options else 0

    idx = st.selectbox(
        "Transcript",
        range(len(options)),
        format_func=lambda i: labels[i],
        index=default_idx,
        key="speaker_id_transcript",
    )
    transcript_path = options[idx]

    # Re-load whenever transcript changes
    prev_key = "speaker_id_prev_transcript"
    if st.session_state.get(prev_key) != transcript_path:
        st.session_state[prev_key] = transcript_path
        st.session_state["speaker_id_speaker_idx"] = 0
        st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
        st.session_state["speaker_id_play_seg"] = None

    # ── load segments + map ───────────────────────────────────────────────────
    segments = controller.list_segments(transcript_path)
    if not segments:
        st.info("No segments found in this transcript.")
        return

    map_state = controller.get_mapping_status(transcript_path)
    speaker_map: Dict[str, str] = map_state.speaker_map or {}
    ignored: List[str] = getattr(map_state, "ignored_speakers", None) or []

    groups = _group_by_diarized_id(segments)
    speaker_ids = list(groups.keys())
    total_speakers = len(speaker_ids)

    if total_speakers == 0:
        st.info("No speaker IDs found in this transcript.")
        return

    audio_path = controller.get_audio_path(transcript_path)

    # ── progress summary ──────────────────────────────────────────────────────
    named = sum(
        1
        for sid in speaker_ids
        if (speaker_map.get(sid) or "").strip() and sid not in ignored
    )
    n_ignored = sum(1 for sid in speaker_ids if sid in ignored)
    remaining = total_speakers - named - n_ignored

    col_a, col_b, col_c, col_d = st.columns(4)
    col_a.metric("Speakers", total_speakers)
    col_b.metric("Named", named)
    col_c.metric("Ignored", n_ignored)
    col_d.metric("Remaining", remaining)

    if remaining == 0 and total_speakers > 0:
        st.success("All speakers identified!")

    st.divider()

    # ── speaker navigation state ──────────────────────────────────────────────
    speaker_idx = st.session_state.get("speaker_id_speaker_idx", 0)
    if speaker_idx >= total_speakers:
        speaker_idx = 0
        st.session_state["speaker_id_speaker_idx"] = 0

    active_id = speaker_ids[speaker_idx]
    active_segs = groups[active_id]
    current_name = speaker_map.get(active_id, "")
    is_ignored = active_id in ignored

    # ── speaker header ────────────────────────────────────────────────────────
    status_badge = (
        "🔇 ignored"
        if is_ignored
        else (f"✅ **{current_name}**" if current_name.strip() else "❓ unnamed")
    )
    st.subheader(
        f"Speaker {speaker_idx + 1} / {total_speakers} — `{active_id}` {status_badge}"
    )
    lines_shown = st.session_state.get("speaker_id_lines_shown", _LINES_PER_PAGE)
    total_dur = sum(max(0.0, s.end - s.start) for s in active_segs)
    st.caption(
        f"{len(active_segs)} segments · {_fmt_time(total_dur)} total · "
        f"showing {min(lines_shown, len(active_segs))} of {len(active_segs)} lines"
    )

    # ── playback panel (fragment) ─────────────────────────────────────────────
    # Only this region reruns on play-button clicks; the rest of the page is
    # unaffected.  All expensive data work was done above and is passed in.
    render_playback_panel(
        controller=controller,
        transcript_path=transcript_path,
        audio_path=audio_path,
        all_segs=active_segs,
        active_id=active_id,
        play_key="speaker_id_play_seg",
        lines_key="speaker_id_lines_shown",
        max_lines=_LINES_PER_PAGE,
        autoplay=True,
        include_segment_rows=True,
    )

    st.divider()

    # ── name assignment ───────────────────────────────────────────────────────
    col_name, col_save, col_ignore = st.columns([3, 1, 1])
    with col_name:
        name_input = st.text_input(
            "Assign name",
            value=current_name,
            key=f"sid_name_{active_id}",
            placeholder="Type speaker name…",
            label_visibility="collapsed",
        )
    with col_save:
        if st.button(
            "Save name", key="sid_save", type="primary", use_container_width=True
        ):
            name = (name_input or "").strip()
            if name:
                try:
                    controller.apply_mapping_mutation(
                        transcript_path, active_id, name, method="web"
                    )
                    st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
                    st.session_state["speaker_id_play_seg"] = None
                    # Advance to next unnamed speaker automatically
                    next_idx = _next_unnamed_idx(
                        speaker_ids,
                        speaker_map | {active_id: name},
                        ignored,
                        speaker_idx,
                    )
                    st.session_state["speaker_id_speaker_idx"] = next_idx
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            else:
                st.warning("Enter a name before saving.")
    with col_ignore:
        ignore_label = "Unignore" if is_ignored else "Ignore"
        if st.button(ignore_label, key="sid_ignore", use_container_width=True):
            try:
                if is_ignored:
                    controller.unignore_speaker(
                        transcript_path, active_id, method="web"
                    )
                else:
                    controller.ignore_speaker(transcript_path, active_id, method="web")
                st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
                st.session_state["speaker_id_play_seg"] = None
                next_idx = _next_unnamed_idx(
                    speaker_ids, speaker_map, ignored + [active_id], speaker_idx
                )
                st.session_state["speaker_id_speaker_idx"] = next_idx
                st.rerun()
            except Exception as e:
                st.error(str(e))

    # ── prev / next navigation ────────────────────────────────────────────────
    st.divider()
    col_prev, col_jump, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button(
            "← Prev",
            key="sid_prev",
            disabled=(speaker_idx == 0),
            use_container_width=True,
        ):
            st.session_state["speaker_id_speaker_idx"] = speaker_idx - 1
            st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
            st.session_state["speaker_id_play_seg"] = None
            st.rerun()
    with col_jump:
        # Jump-to picker: show all speakers with their current status
        jump_labels = [
            _speaker_label(sid, i, speaker_map, ignored)
            for i, sid in enumerate(speaker_ids)
        ]
        jump_idx = st.selectbox(
            "Jump to speaker",
            range(total_speakers),
            format_func=lambda i: jump_labels[i],
            index=speaker_idx,
            key="sid_jump",
            label_visibility="collapsed",
        )
        if jump_idx != speaker_idx:
            st.session_state["speaker_id_speaker_idx"] = jump_idx
            st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
            st.session_state["speaker_id_play_seg"] = None
            st.rerun()
    with col_next:
        if st.button(
            "Next →",
            key="sid_next",
            disabled=(speaker_idx >= total_speakers - 1),
            use_container_width=True,
        ):
            st.session_state["speaker_id_speaker_idx"] = speaker_idx + 1
            st.session_state["speaker_id_lines_shown"] = _LINES_PER_PAGE
            st.session_state["speaker_id_play_seg"] = None
            st.rerun()


# ── utilities ─────────────────────────────────────────────────────────────────


def _speaker_label(
    sid: str,
    idx: int,
    speaker_map: Dict[str, str],
    ignored: List[str],
) -> str:
    name = (speaker_map.get(sid) or "").strip()
    if sid in ignored:
        return f"{idx + 1}. {sid} 🔇"
    if name:
        return f"{idx + 1}. {sid} → {name}"
    return f"{idx + 1}. {sid} ❓"


def _next_unnamed_idx(
    speaker_ids: List[str],
    speaker_map: Dict[str, str],
    ignored: List[str],
    current: int,
) -> int:
    """Return index of next speaker that has no name and is not ignored, or stay."""
    ignored_set = set(ignored)
    # Try forward first
    for i in range(current + 1, len(speaker_ids)):
        sid = speaker_ids[i]
        if sid not in ignored_set and not (speaker_map.get(sid) or "").strip():
            return i
    # Then try from the beginning
    for i in range(0, current):
        sid = speaker_ids[i]
        if sid not in ignored_set and not (speaker_map.get(sid) or "").strip():
            return i
    return current
