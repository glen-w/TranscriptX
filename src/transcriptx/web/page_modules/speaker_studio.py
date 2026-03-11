"""
Speaker Studio: browser-first speaker identification with instant audio playback.

Shown only when TRANSCRIPTX_ENABLE_SPEAKER_STUDIO=1 (e.g. transcriptx-studio service).
Calls only SpeakerStudioController (no direct service imports).

The audio player is rendered via render_playback_panel() (@st.fragment) with
include_segment_rows=False. Segment rows with their assign widgets are rendered
outside the fragment (they need to be able to trigger full reruns for the status
bar). Play buttons in those rows use on_click callbacks to update session state
without an extra explicit st.rerun().
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from transcriptx.app.compat import discover_all_transcript_paths
from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.web.components.playback_panel import (
    _set_play_idx,
    render_playback_panel,
)
from transcriptx.web.services.file_service import FileService

# Non-transcript JSON names under run dirs (skip when scanning outputs)
_RUN_DIR_JSON_SKIP = frozenset(
    {"manifest.json", "run_results.json", "processing_state.json"}
)


@st.cache_data(ttl=120, show_spinner=False)
def _transcript_paths_for_speaker_views() -> list:
    """Cached so transcript dropdown/selection doesn't trigger full discovery on every rerun."""
    return _transcript_paths_for_speaker_views_impl()


def _transcript_paths_for_speaker_views_impl() -> list[Path]:
    """Same discovery as Library and session-based views; also scan run dirs (Docker-friendly)."""
    paths: list[Path] = []
    seen: set[str] = set()

    def add(p: Path) -> None:
        key = str(p.resolve())
        if key not in seen and p.exists():
            seen.add(key)
            paths.append(p)

    for p in discover_all_transcript_paths(None):
        add(Path(p))

    for session in FileService.list_available_sessions():
        name = session.get("name", "")
        if "/" not in name:
            continue
        resolved = FileService.resolve_transcript_path(name)
        if resolved:
            add(Path(resolved))

    # Docker: manifest transcript_path is often host-only; scan run dirs for transcript-like JSON
    from transcriptx.core.utils.paths import OUTPUTS_DIR

    outputs_dir = Path(OUTPUTS_DIR)
    if outputs_dir.is_dir():
        for slug_dir in outputs_dir.iterdir():
            if not slug_dir.is_dir() or slug_dir.name.startswith("."):
                continue
            for run_dir in slug_dir.iterdir():
                if not run_dir.is_dir() or run_dir.name.startswith("."):
                    continue
                for j in run_dir.glob("*.json"):
                    if (
                        j.name in _RUN_DIR_JSON_SKIP
                        or j.parent.name == ".transcriptx"
                        or j.name.endswith("_stats.json")
                    ):
                        continue
                    add(j)

    return sorted(paths, key=lambda p: str(p.resolve()))


@st.cache_data(ttl=120, show_spinner=False)
def _cached_transcripts_for_paths(paths_key: tuple[str, ...]) -> list:
    """Return transcript list for given paths so selectbox/UI doesn't recompute on every rerun."""
    if not paths_key:
        return []
    controller = SpeakerStudioController()
    paths = [Path(p) for p in paths_key]
    return controller.list_transcripts_from_paths(paths)


@st.cache_data(ttl=120, show_spinner=False)
def _cached_speaker_studio_fallback_transcripts() -> list:
    """Fallback when no paths from discovery; avoids full list_transcripts on every rerun."""
    controller = SpeakerStudioController()
    try:
        return controller.list_transcripts(canonical_only=False)
    except TypeError:
        return controller.list_transcripts()


def render_speaker_studio() -> None:
    st.markdown(
        '<div class="main-header">🎙️ Speaker Studio</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Identify speakers with instant playback. Select a transcript, then play segments and assign names."
    )

    controller = SpeakerStudioController()
    paths = _transcript_paths_for_speaker_views()
    if paths:
        paths_key = tuple(str(p) for p in paths)
        transcripts = _cached_transcripts_for_paths(paths_key)
    else:
        transcripts = []
    if not transcripts:
        transcripts = _cached_speaker_studio_fallback_transcripts()
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

    # Prev/Next navigation (outside fragment — intentional full rerun)
    if audio_path and segments:
        col_prev, _col_mid, col_next = st.columns([1, 2, 1])
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

    # Audio player fragment — only this region reruns when active_index changes
    # via on_click callbacks in the rows below.  The rows themselves stay outside
    # the fragment so their Save buttons can trigger full reruns to refresh the
    # status bar.
    render_playback_panel(
        controller=controller,
        transcript_path=transcript_path,
        audio_path=audio_path,
        all_segs=segments,
        active_id="studio",
        play_key="speaker_studio_active_index",
        lines_key="speaker_studio_lines_shown",
        max_lines=len(segments),
        autoplay=False,
        include_segment_rows=False,
    )

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
            if audio_path:
                # on_click sets state before the natural rerun — no explicit
                # st.rerun() needed.
                st.button(
                    "▶",
                    key=f"studio_play_{i}",
                    on_click=_set_play_idx,
                    args=("speaker_studio_active_index", i),
                )
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
