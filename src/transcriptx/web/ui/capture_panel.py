"""Thin Transcribe Audio panel for G5 Mac system-audio capture."""

from __future__ import annotations

import streamlit as st

from transcriptx.web import icons as ic
from transcriptx.services.capture.host_control import (
    capture_controls_available,
    list_capture_status,
    start_capture,
    stop_capture,
)


def render_system_audio_capture_panel() -> None:
    st.subheader("System audio capture (Mac)")
    if not capture_controls_available():
        st.caption(
            "Capture runs on the **Mac host** via BlackHole "
            "(`scripts/system-audio-capture.py`). Docker Compose cannot see "
            "Mac loopback. Docs: docs/runtime/system-audio-capture.md."
        )
        return

    st.caption(
        "Records computer audio (BlackHole + Multi-Output Device), then on Stop "
        "runs host whispermlx and writes WhisperX JSON under originals/. "
        "Not a meeting bot. Live captions are theme H6."
    )
    status = list_capture_status()
    if status:
        st.write(
            f"**{status.get('state', 'unknown')}** · "
            f"{status.get('title') or status.get('session_id', '')}"
        )
        for warning in status.get("warnings") or []:
            st.warning(str(warning))
        for error in status.get("errors") or []:
            st.error(str(error))
    else:
        st.caption("No capture session.")

    title = st.text_input("Session title", key="tx_g5_capture_title")
    mix_mic = st.checkbox(
        "Mix microphone",
        key="tx_g5_capture_mix_mic",
        help="Optional. Use when you are on headphones and need your voice too.",
    )
    admit = st.checkbox(
        "Admit into library on Stop",
        key="tx_g5_capture_admit",
        help="Default off, same as inbox-watch --admit. JSON still lands in originals/.",
    )
    col_start, col_stop = st.columns(2)
    with col_start:
        if st.button("Start capture", key="tx_g5_capture_start", icon=ic.PLAY):
            result = start_capture(title=title, mix_mic=mix_mic)
            if result.returncode == 0:
                st.success(result.stdout.strip() or "Recording started.")
            else:
                st.error((result.stderr or result.stdout or "Start failed.").strip())
            st.rerun()
    with col_stop:
        if st.button("Stop capture", key="tx_g5_capture_stop", icon=ic.STOP):
            result = stop_capture(admit=admit)
            if result.returncode == 0:
                st.success(result.stdout.strip() or "Stopped.")
            else:
                st.error((result.stderr or result.stdout or "Stop failed.").strip())
            st.rerun()
