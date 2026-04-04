"""Settings storage roots informational subview."""

from __future__ import annotations

import streamlit as st

from transcriptx.app.controllers.settings_controller import SettingsController


def render_storage_panel() -> None:
    """Show configured storage root paths (read-only)."""
    st.subheader("Storage roots")
    ctrl = SettingsController()
    roots = ctrl.get_storage_roots()
    for name, path in roots.items():
        st.text(f"{name}: {path}")
