"""Transcript-scoped Streamlit session keys for Speaker ID (shared with CCv2)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import streamlit as st


def _transcript_ns(transcript_path: str | Path) -> str:
    """Stable short namespace from resolved transcript path."""
    try:
        resolved = str(Path(transcript_path).resolve())
    except OSError:
        resolved = str(transcript_path)
    return hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:12]


def speaker_idx_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:speaker_idx"


def jump_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:jump"


def play_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:play_seg"


def lines_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:lines_shown"


def name_widget_key(transcript_path: str | Path, speaker_id: str) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:name:{speaker_id}"


def link_profile_key(transcript_path: str | Path, speaker_id: str) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:link:{speaker_id}"


def link_mode_key(transcript_path: str | Path, speaker_id: str) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:link_mode:{speaker_id}"


def voice_pending_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:voice_pending"


def voice_loaded_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:voice_loaded"


def voice_batch_summary_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:voice_batch_summary"


def flash_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:flash"


def widget_key(transcript_path: str | Path, suffix: str) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:{suffix}"


@dataclass(frozen=True)
class TranscriptProfileContext:
    """Immutable managed-transcript gate for Speaker ID UI."""

    is_managed: bool
    managed_transcript_id: str | None = None


def voice_display_key(transcript_path: str | Path, speaker_id: str) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:voice_display:{speaker_id}"


def voice_gate_key(transcript_path: str | Path) -> str:
    return f"sid:{_transcript_ns(transcript_path)}:voice_gate"


def _set_flash(
    transcript_path: str | Path,
    *,
    level: str,
    message: str,
) -> None:
    st.session_state[flash_key(transcript_path)] = {
        "level": level,
        "message": message,
    }


def _consume_flash(transcript_path: str | Path) -> None:
    payload = st.session_state.pop(flash_key(transcript_path), None)
    if not payload or not isinstance(payload, dict):
        return
    level = str(payload.get("level") or "info")
    message = str(payload.get("message") or "").strip()
    if not message:
        return
    if level == "error":
        st.error(message)
    elif level == "warning":
        st.warning(message)
    elif level == "success":
        st.success(message)
    else:
        st.info(message)
