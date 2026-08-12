"""Accessible info control for raw run identifiers (no Streamlit widgets)."""

from __future__ import annotations

import uuid

import streamlit as st

from transcriptx.web.components.info_tooltip import build_info_tooltip_html


def build_run_id_info_html(raw_run_id: str, *, control_id: str | None = None) -> str:
    """Build escaped HTML for a keyboard-focusable run-id info control.

    Uses a custom hover/focus tooltip (not title-attribute-only).
    Does not mutate application state.
    """
    tip_id = control_id or f"tx-run-tip-{uuid.uuid4().hex[:12]}"
    return build_info_tooltip_html(
        str(raw_run_id),
        control_id=tip_id,
        aria_label=f"Full run identifier: {raw_run_id}",
        test_id="tx-run-id-info",
        tip_extra_class="",
        wrap_extra_class="",
    )


def render_run_id_info_control(
    raw_run_id: str | None, *, key: str | None = None
) -> None:
    """Render the info control when a non-empty raw run id is available."""
    if not raw_run_id or not str(raw_run_id).strip():
        return
    control_id = None
    if key:
        safe = "".join(ch if ch.isalnum() else "-" for ch in str(key))[:48]
        control_id = f"tx-run-tip-{safe}" if safe else None
    st.markdown(
        build_run_id_info_html(str(raw_run_id).strip(), control_id=control_id),
        unsafe_allow_html=True,
    )
