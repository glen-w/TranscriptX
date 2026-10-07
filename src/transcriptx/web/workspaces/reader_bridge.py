"""Assemble CCv2 Theme D reader workspace data (full-file loopback playback)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.web.components.playback_panel import resolve_playback_context
from transcriptx.web.media_route import get_media_route, loopback_host_allowed
from transcriptx.web.transcript_viewer.karaoke_timing import build_reader_segment
from transcriptx_workspaces import FRONTEND_BUILD_ID, PROTOCOL_VERSION

_PAYLOAD_CHAR_CAP = 1_500_000


def _fingerprint_str(fp: Optional[tuple[str, int, int]]) -> Optional[str]:
    if fp is None:
        return None
    return f"{fp[1]}:{fp[2]}"


def reader_media_token_key(transcript_scope: str) -> str:
    return f"reader_media_token:{transcript_scope}"


def reader_media_fp_key(transcript_scope: str) -> str:
    return f"reader_media_fp:{transcript_scope}"


def reader_jump_epoch_key(transcript_scope: str) -> str:
    return f"reader_jump_epoch:{transcript_scope}"


def _mint_audio_url(
    session_state: dict[str, Any],
    *,
    transcript_scope: str,
    audio_path: Path,
    fingerprint: tuple[str, int, int],
) -> Optional[str]:
    fp_str = _fingerprint_str(fingerprint)
    token_key = reader_media_token_key(transcript_scope)
    fp_key = reader_media_fp_key(transcript_scope)
    if session_state.get(fp_key) == fp_str and session_state.get(token_key):
        token = str(session_state[token_key])
        try:
            route = get_media_route()
            if route.available:
                return route.audio_url(token)
        except RuntimeError:
            pass
    try:
        route = get_media_route()
        token = route.mint(audio_path)
    except (OSError, ValueError, RuntimeError):
        return None
    session_state[token_key] = token
    session_state[fp_key] = fp_str
    return route.audio_url(token)


def build_reader_workspace_data(
    *,
    controller: SpeakerStudioController,
    transcript_path: str,
    transcript_scope: str,
    transcript_revision: str,
    segments: Sequence[Mapping[str, Any]],
    session_state: dict[str, Any],
    search_text: str,
    show_unnamed: bool,
    jump_epoch: int,
    jump_index: Optional[int],
    autoplay_jump: bool,
) -> dict[str, Any]:
    """JSON-serialisable ``data=`` for ``reader_workspace``."""
    playback = resolve_playback_context(controller, transcript_path)
    audio_url: Optional[str] = None
    unavailable: Optional[str] = None
    audio_ready = False

    if not loopback_host_allowed():
        unavailable = "media_route_off"
    elif playback.audio_path is None or playback.audio_fingerprint is None:
        unavailable = "no_audio"
    else:
        audio_url = _mint_audio_url(
            session_state,
            transcript_scope=transcript_scope,
            audio_path=playback.audio_path,
            fingerprint=playback.audio_fingerprint,
        )
        if audio_url is None:
            unavailable = "media_route_off"
        else:
            audio_ready = True

    reader_segments = [
        build_reader_segment(seg, idx) for idx, seg in enumerate(segments)
    ]

    payload: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "frontend_build_id": FRONTEND_BUILD_ID,
        "transcript_id": transcript_scope,
        "transcript_revision": transcript_revision,
        "audio_url": audio_url,
        "audio_fingerprint": _fingerprint_str(playback.audio_fingerprint),
        "audio_ready": audio_ready,
        "unavailable_reason": unavailable,
        "search_text": search_text or "",
        "show_unnamed": bool(show_unnamed),
        "jump_epoch": int(jump_epoch),
        "jump_index": jump_index,
        "autoplay_jump": bool(autoplay_jump),
        "segments": reader_segments,
        "word_timing_omitted": False,
    }

    if len(json.dumps(payload, ensure_ascii=False)) > _PAYLOAD_CHAR_CAP:
        for seg in reader_segments:
            seg["mode"] = "segment"
            seg["words"] = [{"t": w["t"]} for w in seg.get("words", [])]
        payload["word_timing_omitted"] = True

    return payload


def render_reader_workspace(
    *,
    controller: SpeakerStudioController,
    transcript_path: str,
    transcript_scope: str,
    transcript_revision: str,
    segments: Sequence[Mapping[str, Any]],
    search_text: str,
    show_unnamed: bool,
    jump_epoch: int,
    jump_index: Optional[int],
    autoplay_jump: bool,
    component_key: str,
) -> bool:
    """Mount the reader CCv2 component. Returns False when the package is missing."""
    import streamlit as st

    try:
        from transcriptx_workspaces import reader_workspace
    except ImportError:
        st.error(
            "Theme D reader requires `transcriptx-workspaces`. "
            "Install with: pip install -e \".[web]\""
        )
        return False

    data = build_reader_workspace_data(
        controller=controller,
        transcript_path=transcript_path,
        transcript_scope=transcript_scope,
        transcript_revision=transcript_revision,
        segments=segments,
        session_state=st.session_state,
        search_text=search_text,
        show_unnamed=show_unnamed,
        jump_epoch=jump_epoch,
        jump_index=jump_index,
        autoplay_jump=autoplay_jump,
    )
    reader_workspace(data=data, key=component_key, height=720)
    return True
