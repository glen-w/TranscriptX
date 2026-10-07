"""TranscriptX CCv2 workspace components (Theme C)."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

FRONTEND_BUILD_ID = "tx-workspaces-0.3.0"
PROTOCOL_VERSION = "1"

_speaker_id_component = None
_corrections_component = None
_viewer_edit_component = None
_reader_component = None


def _noop() -> None:
    """Stable no-op for unused CCv2 ``on_*_change`` callbacks."""
    return None


_SPEAKER_ID_HTML = """
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
                  <input type="text" class="tx-sid-name-input" list="tx-sid-name-datalist" autocomplete="off" />
                  <datalist class="tx-sid-name-datalist" id="tx-sid-name-datalist"></datalist>
                  <select class="tx-sid-name-pick" aria-label="Suggested names">
                    <option value="">Suggested names…</option>
                  </select>
                </label>
                <p class="tx-sid-name-hint" aria-live="polite"></p>
                <div class="tx-sid-roster" hidden>
                  <div class="tx-sid-roster-title">People mentioned</div>
                  <ul class="tx-sid-roster-list"></ul>
                </div>
                <label class="tx-sid-link-label">
                  <span>Profile</span>
                  <select class="tx-sid-link-select"></select>
                </label>
                <p class="tx-sid-link-chip" aria-live="polite"></p>
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
              <div class="tx-sid-paging" hidden></div>
            </section>
          </div>
          <div class="tx-sid-help" hidden></div>
        </div>
    """

_CORRECTIONS_HTML = """
        <div class="tx-corr-root" data-testid="corrections-workspace" tabindex="0">
          <aside class="tx-corr-list" aria-label="Candidates"></aside>
          <section class="tx-corr-detail">
            <div class="tx-corr-status" aria-live="polite"></div>
            <div class="tx-corr-kind"></div>
            <p class="tx-corr-wrong"></p>
            <label>
              <span>Replacement</span>
              <input type="text" class="tx-corr-draft" autocomplete="off" />
            </label>
            <div class="tx-corr-actions">
              <button type="button" class="tx-corr-accept">Accept</button>
              <button type="button" class="tx-corr-reject">Reject</button>
              <button type="button" class="tx-corr-skip">Skip</button>
              <button type="button" class="tx-corr-save-draft">Save draft</button>
            </div>
          </section>
        </div>
    """

_VIEWER_EDIT_HTML = """
        <div class="tx-vedit-root" data-testid="viewer-edit-workspace" tabindex="0">
          <div class="tx-vedit-words"></div>
          <p class="tx-vedit-caption"></p>
        </div>
    """

_READER_HTML = """
        <div class="tx-reader-root" data-testid="tx-reader-root" tabindex="0">
          <p class="tx-reader-caption" aria-live="polite"></p>
          <audio class="tx-reader-audio" controls preload="metadata"></audio>
          <p class="tx-reader-status"></p>
          <div class="tx-reader-scroll"></div>
        </div>
    """


def _get_speaker_id_component():
    """Lazy-register so import works outside ``streamlit run`` (tests/wheel checks)."""
    global _speaker_id_component
    if _speaker_id_component is not None:
        return _speaker_id_component
    import streamlit as st

    _speaker_id_component = st.components.v2.component(
        "transcriptx-workspaces.speaker_id_workspace",
        js="speaker_id-*.js",
        css="speaker_id-styles.css",
        html=_SPEAKER_ID_HTML,
    )
    return _speaker_id_component


def _get_corrections_component():
    global _corrections_component
    if _corrections_component is not None:
        return _corrections_component
    import streamlit as st

    _corrections_component = st.components.v2.component(
        "transcriptx-workspaces.corrections_workspace",
        js="corrections-*.js",
        css="corrections-styles.css",
        html=_CORRECTIONS_HTML,
    )
    return _corrections_component


def _get_reader_component():
    global _reader_component
    if _reader_component is not None:
        return _reader_component
    import streamlit as st

    _reader_component = st.components.v2.component(
        "transcriptx-workspaces.reader_workspace",
        js="reader-*.js",
        css="reader-styles.css",
        html=_READER_HTML,
    )
    return _reader_component


def _get_viewer_edit_component():
    global _viewer_edit_component
    if _viewer_edit_component is not None:
        return _viewer_edit_component
    import streamlit as st

    _viewer_edit_component = st.components.v2.component(
        "transcriptx-workspaces.viewer_edit_workspace",
        js="viewer_edit-*.js",
        css="viewer_edit-styles.css",
        html=_VIEWER_EDIT_HTML,
    )
    return _viewer_edit_component


def speaker_id_workspace(
    *,
    data: Mapping[str, Any],
    key: str,
    default: Optional[Mapping[str, Any]] = None,
    on_command_change: Optional[Callable[[], None]] = None,
    on_ack_seq_change: Optional[Callable[[], None]] = None,
    height: str | int = "content",
) -> Any:
    """Mount the Speaker ID CCv2 workspace with a stable transcript-scoped key."""
    comp = _get_speaker_id_component()
    kwargs: dict[str, Any] = {
        "data": dict(data),
        "key": key,
        "default": dict(default or {"ack_seq": 0}),
        "height": height,
        "on_command_change": on_command_change or _noop,
        "on_ack_seq_change": on_ack_seq_change or _noop,
    }
    return comp(**kwargs)


def corrections_workspace(
    *,
    data: Mapping[str, Any],
    key: str,
    default: Optional[Mapping[str, Any]] = None,
    on_command_change: Optional[Callable[[], None]] = None,
    on_ack_seq_change: Optional[Callable[[], None]] = None,
    height: str | int = "content",
) -> Any:
    """Mount the Corrections Studio review CCv2 workspace."""
    comp = _get_corrections_component()
    kwargs: dict[str, Any] = {
        "data": dict(data),
        "key": key,
        "default": dict(default or {"ack_seq": 0}),
        "height": height,
        "on_command_change": on_command_change or _noop,
        "on_ack_seq_change": on_ack_seq_change or _noop,
    }
    return comp(**kwargs)


def reader_workspace(
    *,
    data: Mapping[str, Any],
    key: str,
    height: str | int = 720,
) -> Any:
    """Mount the Theme D transcript reader (full-file loopback playback)."""
    comp = _get_reader_component()
    return comp(data=dict(data), key=key, height=height)


def viewer_edit_workspace(
    *,
    data: Mapping[str, Any],
    key: str,
    default: Optional[Mapping[str, Any]] = None,
    on_selection_change: Optional[Callable[[], None]] = None,
    height: str | int = "content",
) -> Any:
    """Mount the Transcript Correct-mode word-span selector."""
    comp = _get_viewer_edit_component()
    kwargs: dict[str, Any] = {
        "data": dict(data),
        "key": key,
        "default": dict(default or {"selection": None}),
        "height": height,
        "on_selection_change": on_selection_change or _noop,
    }
    return comp(**kwargs)


__all__ = [
    "FRONTEND_BUILD_ID",
    "PROTOCOL_VERSION",
    "corrections_workspace",
    "reader_workspace",
    "speaker_id_workspace",
    "viewer_edit_workspace",
]
