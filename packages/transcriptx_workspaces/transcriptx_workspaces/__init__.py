"""TranscriptX CCv2 workspace components (Theme C)."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

FRONTEND_BUILD_ID = "tx-workspaces-0.1.0"
PROTOCOL_VERSION = "1"

_speaker_id_component = None


def _noop() -> None:
    """Stable no-op for unused CCv2 ``on_*_change`` callbacks."""
    return None


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
                  <button type="button" class="tx-sid-save tx-sid-icon-btn" aria-label="Save" title="Save">
                    <svg class="tx-sid-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path fill="currentColor" d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z"/>
                    </svg>
                  </button>
                  <button type="button" class="tx-sid-ignore tx-sid-icon-btn" aria-label="Ignore" title="Ignore">
                    <svg class="tx-sid-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path fill="currentColor" d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 2a8 8 0 0 1 6.32 12.9L7.1 5.68A7.96 7.96 0 0 1 12 4zm0 16a8 8 0 0 1-6.32-12.9L16.9 18.32A7.96 7.96 0 0 1 12 20z"/>
                    </svg>
                  </button>
                  <button type="button" class="tx-sid-prev tx-sid-icon-btn" aria-label="Previous" title="Previous">
                    <svg class="tx-sid-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path fill="currentColor" d="M15.41 7.41 14 6l-6 6 6 6 1.41-1.41L10.83 12z"/>
                    </svg>
                  </button>
                  <button type="button" class="tx-sid-next tx-sid-icon-btn" aria-label="Next" title="Next">
                    <svg class="tx-sid-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path fill="currentColor" d="M10 6 8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z"/>
                    </svg>
                  </button>
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
        # ``ack_seq`` is persistent component *state* (setStateValue).
        # ``command`` must NOT be in ``default``: that would register it as
        # state, and Streamlit's ComponentResult / presenter merge state *over*
        # triggers — wiping every setTriggerValue("command", …) envelope to
        # the default ``None`` before Python can apply navigate/save/ignore.
        # Register ``on_command_change`` only so ``command`` stays a trigger.
        "default": dict(default or {"ack_seq": 0}),
        "height": height,
        # Streamlit CCv2 only accepts ``default`` keys that have matching
        # ``on_{name}_change`` callbacks. Always register both protocol
        # callbacks (state + trigger) even when the caller does not consume them.
        "on_command_change": on_command_change or _noop,
        "on_ack_seq_change": on_ack_seq_change or _noop,
    }
    return comp(**kwargs)


__all__ = [
    "FRONTEND_BUILD_ID",
    "PROTOCOL_VERSION",
    "speaker_id_workspace",
]
