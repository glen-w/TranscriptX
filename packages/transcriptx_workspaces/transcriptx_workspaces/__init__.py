"""TranscriptX CCv2 workspace components (Theme C)."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

FRONTEND_BUILD_ID = "tx-workspaces-0.1.0"
PROTOCOL_VERSION = "1"

_speaker_id_component = None


def _get_speaker_id_component():
    """Lazy-register so import works outside ``streamlit run`` (tests/wheel checks)."""
    global _speaker_id_component
    if _speaker_id_component is not None:
        return _speaker_id_component
    import streamlit as st

    _speaker_id_component = st.components.v2.component(
        "transcriptx-workspaces.speaker_id_workspace",
        js="index-*.js",
        css="index-*.css",
        html="""
        <div class="tx-sid-root" data-testid="speaker-id-workspace">
          <div class="tx-sid-header">
            <div class="tx-sid-title"></div>
            <div class="tx-sid-status" aria-live="polite"></div>
          </div>
          <div class="tx-sid-body">
            <aside class="tx-sid-speakers" aria-label="Speakers"></aside>
            <section class="tx-sid-main">
              <div class="tx-sid-player">
                <audio class="tx-sid-audio" preload="auto" controls></audio>
                <div class="tx-sid-clip-status"></div>
              </div>
              <div class="tx-sid-naming">
                <label class="tx-sid-name-label">
                  <span>Name</span>
                  <input type="text" class="tx-sid-name-input" autocomplete="off" />
                </label>
                <label class="tx-sid-link-label">
                  <input type="checkbox" class="tx-sid-link-profile" />
                  <span>Link profile</span>
                </label>
                <div class="tx-sid-actions">
                  <button type="button" class="tx-sid-save">Save</button>
                  <button type="button" class="tx-sid-ignore">Ignore</button>
                  <button type="button" class="tx-sid-prev">Prev</button>
                  <button type="button" class="tx-sid-next">Next</button>
                </div>
              </div>
              <ol class="tx-sid-samples" aria-label="Sample lines"></ol>
            </section>
          </div>
          <div class="tx-sid-help" hidden></div>
        </div>
    """,
    )
    return _speaker_id_component


def speaker_id_workspace(
    *,
    data: Mapping[str, Any],
    key: str,
    default: Optional[Mapping[str, Any]] = None,
    on_command_change: Optional[Callable[[], None]] = None,
    on_ack_seq_change: Optional[Callable[[], None]] = None,
    height: str | int = "content",
) -> Any:
    """Mount the Speaker ID CCv2 workspace with a stable transcript-scoped key.

    ``key`` must be stable for a given transcript (e.g. ``speaker_id_ws:{id}``)
    so metadata/mapping/clip updates do not remount the frontend identity.
    """
    comp = _get_speaker_id_component()
    kwargs: dict[str, Any] = {
        "data": dict(data),
        "key": key,
        "default": dict(
            default
            or {
                "ack_seq": 0,
                "command": None,
            }
        ),
        "height": height,
    }
    if on_command_change is not None:
        kwargs["on_command_change"] = on_command_change
    if on_ack_seq_change is not None:
        kwargs["on_ack_seq_change"] = on_ack_seq_change
    return comp(**kwargs)


__all__ = [
    "FRONTEND_BUILD_ID",
    "PROTOCOL_VERSION",
    "speaker_id_workspace",
]
