"""Diff view helpers for config changes."""

from __future__ import annotations

from typing import Any, Dict
import streamlit as st

from transcriptx.core.config.registry import flatten


def render_config_diff(base_config: Dict[str, Any], modified_config: Dict[str, Any]) -> None:
    """Render a simple diff between two config dicts."""
    base = flatten(base_config)
    modified = flatten(modified_config)
    changes = []
    all_keys = set(base.keys()) | set(modified.keys())
    for key in sorted(all_keys):
        if base.get(key) != modified.get(key):
            changes.append(f"{key}: {base.get(key)} → {modified.get(key)}")
    if not changes:
        st.caption("No changes.")
        return
    st.markdown("**Changes**")
    for change in changes:
        st.write(change)
