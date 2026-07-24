"""Shared presentation-mode switch widget for Home / Settings.

Simple on/off: Guided mode on → Guided; off → Full controls.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from transcriptx.web.presentation.prefs import MODE_FULL, MODE_GUIDED
from transcriptx.web.presentation.resolve import (
    PENDING_SYNC_KEY,
    WIDGET_KEY,
    resolve_presentation_mode,
    set_presentation_mode,
)


def _hydrate_widget(session_state: dict[str, Any]) -> None:
    guided_on = resolve_presentation_mode() == MODE_GUIDED
    current = session_state.get(WIDGET_KEY)
    # Migrate legacy segmented-control string values if still in session.
    if isinstance(current, str):
        session_state[WIDGET_KEY] = current == "Guided"
        current = session_state[WIDGET_KEY]
    if session_state.pop(PENDING_SYNC_KEY, False) or WIDGET_KEY not in session_state:
        session_state[WIDGET_KEY] = guided_on
    elif not isinstance(current, bool):
        session_state[WIDGET_KEY] = guided_on


def render_presentation_mode_switch(*, location: str = "home") -> None:
    """Render Guided mode on/off toggle; persist on change with CAS."""
    _hydrate_widget(st.session_state)
    st.caption(
        "**Guided mode** shows the principal workflow and recommended settings. "
        "Turn it off for **Full controls** (specialist tools and advanced settings). "
        "Presentation only — analysis meaning for the same settings stays identical."
    )
    guided_on = st.toggle(
        "Guided mode",
        key=WIDGET_KEY,
        help="On: Guided. Off: Full controls.",
    )
    desired = MODE_GUIDED if guided_on else MODE_FULL
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
