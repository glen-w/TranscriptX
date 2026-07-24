"""Shared presentation-mode switch widget for Home / Settings."""

from __future__ import annotations

from typing import Any

import streamlit as st

from transcriptx.web.presentation.prefs import MODE_FULL, MODE_GUIDED
from transcriptx.web.presentation.resolve import (
    MODE_LABELS,
    PENDING_SYNC_KEY,
    WIDGET_KEY,
    resolve_presentation_mode,
    set_presentation_mode,
)

_OPTIONS = (MODE_LABELS[MODE_GUIDED], MODE_LABELS[MODE_FULL])
_LABEL_TO_MODE = {
    MODE_LABELS[MODE_GUIDED]: MODE_GUIDED,
    MODE_LABELS[MODE_FULL]: MODE_FULL,
}


def _hydrate_widget(session_state: dict[str, Any]) -> None:
    mode = resolve_presentation_mode()
    label = MODE_LABELS[mode]
    if session_state.pop(PENDING_SYNC_KEY, False) or WIDGET_KEY not in session_state:
        session_state[WIDGET_KEY] = label


def render_presentation_mode_switch(*, location: str = "home") -> None:
    """Render Guided / Full controls switch; persist on change with CAS."""
    _hydrate_widget(st.session_state)
    st.caption(
        "**Guided** shows the principal workflow. **Full controls** reveals "
        "specialist tools and advanced settings. Presentation only — analysis "
        "meaning for the same settings stays identical."
    )
    choice = st.segmented_control(
        "Presentation",
        options=list(_OPTIONS),
        key=WIDGET_KEY,
        label_visibility="collapsed",
    )
    if choice is None:
        return
    desired = _LABEL_TO_MODE.get(str(choice))
    if desired is None:
        return
    current = resolve_presentation_mode()
    if desired == current:
        return
    result = set_presentation_mode(desired)
    if result.ok:
        st.session_state[PENDING_SYNC_KEY] = True
        st.rerun()
    elif result.conflict:
        st.warning(result.error or "Presentation mode changed elsewhere — reloading.")
        st.session_state[PENDING_SYNC_KEY] = True
        st.rerun()
    elif result.error:
        st.error(result.error)
