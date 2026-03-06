"""
Speaker Studio: browser-first speaker identification with instant audio playback.

Shown only when TRANSCRIPTX_ENABLE_SPEAKER_STUDIO=1 (e.g. transcriptx-studio service).
Calls only SpeakerStudioController (no direct service imports).
"""

from __future__ import annotations

import os

import streamlit as st

from transcriptx.services.speaker_studio.controller import SpeakerStudioController


def render_speaker_studio() -> None:
    st.markdown(
        '<div class="main-header">🎙️ Speaker Studio</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Identify speakers with instant playback. Select a transcript, then play segments and assign names."
    )

    controller = SpeakerStudioController()
    try:
        transcripts = controller.list_transcripts(canonical_only=False)
    except TypeError:
        # Older controller without canonical_only: list only canonical-named files
        transcripts = controller.list_transcripts()
    if not transcripts:
        st.info(
            "No transcripts found in the data directory. Add transcript JSON files to get started."
        )
        return

    base_name_counts = {}
    for t in transcripts:
        base_name_counts[t.base_name] = base_name_counts.get(t.base_name, 0) + 1
    options = []
    for t in transcripts:
        label = f"{t.base_name} ({t.speaker_map_status}, {t.segment_count} segments)"
        if base_name_counts.get(t.base_name, 0) > 1:
            label = f"{os.path.basename(t.path)} — {label}"
        options.append(label)
    paths = [t.path for t in transcripts]
    idx = st.selectbox(
        "Transcript",
        range(len(options)),
        format_func=lambda i: options[i],
        key="speaker_studio_transcript_select",
    )
    transcript_path = paths[idx]
    summary = transcripts[idx]

    segments = controller.list_segments(transcript_path)
    audio_path = controller.get_audio_path(transcript_path)

    st.session_state.setdefault("speaker_studio_active_index", 0)
    active_index = st.session_state.speaker_studio_active_index
    if active_index >= len(segments):
        active_index = max(0, len(segments) - 1)
        st.session_state.speaker_studio_active_index = active_index

    # Single audio player + Prev/Next
    if audio_path and segments:
        col_prev, col_play, col_next = st.columns([1, 2, 1])
        with col_prev:
            if st.button("⬅ Prev", key="studio_prev"):
                st.session_state.speaker_studio_active_index = max(0, active_index - 1)
                st.rerun()
        with col_next:
            if st.button("Next ➡", key="studio_next"):
                st.session_state.speaker_studio_active_index = min(
                    len(segments) - 1, active_index + 1
                )
                st.rerun()

        active_seg = segments[active_index] if segments else None
        if active_seg and audio_path:
            try:
                clip_bytes = controller.get_clip_bytes(
                    transcript_path,
                    active_seg.start,
                    active_seg.end,
                    format="mp3",
                )
                st.audio(clip_bytes, format="audio/mpeg")
            except Exception as e:
                st.warning(f"Could not load clip: {e}")
    elif not audio_path and segments:
        st.warning("No audio file found for this transcript; playback unavailable.")

    # Status bar
    state = controller.get_mapping_status(transcript_path)
    mapped_count = len(
        [k for k, v in (state.speaker_map or {}).items() if v and str(v).strip()]
    )
    total_speakers = summary.unique_speaker_count or 1
    st.caption(
        f"Speaker map: **{mapped_count}/{total_speakers}** mapped — status: **{summary.speaker_map_status}**"
    )

    st.divider()
    st.subheader("Segments")

    if not segments:
        st.info("No segments in this transcript.")
        return

    for i, seg in enumerate(segments):
        is_active = i == active_index
        col_speaker, col_time, col_text, col_play, col_assign = st.columns(
            [1, 1, 3, 0.5, 1.5]
        )
        with col_speaker:
            st.text(seg.speaker or "(none)")
        with col_time:
            st.text(f"{seg.start:.1f}s – {seg.end:.1f}s")
        with col_text:
            st.text(
                (seg.text or "")[:120] + ("..." if len(seg.text or "") > 120 else "")
            )
        with col_play:
            if audio_path and st.button("▶", key=f"play_{i}"):
                st.session_state.speaker_studio_active_index = i
                st.rerun()
        with col_assign:
            diarized_id = seg.speaker_diarized_id or seg.speaker
            current_name = (state.speaker_map or {}).get(diarized_id) or ""
            new_name = st.text_input(
                "Name",
                value=current_name,
                key=f"assign_{i}_{diarized_id}",
                label_visibility="collapsed",
                placeholder="Display name",
            )
            if st.button("Save", key=f"save_assign_{i}"):
                name = (new_name or "").strip()
                if name:
                    try:
                        controller.apply_mapping_mutation(
                            transcript_path,
                            diarized_id,
                            name,
                            method="web",
                        )
                        st.success("Saved")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.warning("Enter a name")

    # Ignore speaker
    st.divider()
    unique_speakers = list(
        dict.fromkeys((s.speaker_diarized_id or s.speaker) for s in segments)
    )
    ignore_id = st.selectbox(
        "Ignore speaker (diarized ID)",
        [""] + unique_speakers,
        key="studio_ignore_select",
    )
    if ignore_id and st.button("Ignore this speaker", key="studio_ignore_btn"):
        try:
            controller.ignore_speaker(transcript_path, ignore_id, method="web")
            st.success(f"Ignored {ignore_id}")
            st.rerun()
        except Exception as e:
            st.error(str(e))


def is_speaker_studio_enabled() -> bool:
    return os.environ.get("TRANSCRIPTX_ENABLE_SPEAKER_STUDIO") == "1"
