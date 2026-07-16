"""Accessible info control for raw run identifiers (no Streamlit widgets)."""

from __future__ import annotations

import html
import uuid

import streamlit as st


def build_run_id_info_html(raw_run_id: str, *, control_id: str | None = None) -> str:
    """Build escaped HTML for a keyboard-focusable run-id info control.

    Uses a custom hover/focus tooltip (not title-attribute-only).
    Does not mutate application state.
    """
    escaped_id = html.escape(str(raw_run_id), quote=True)
    tip_id = control_id or f"tx-run-tip-{uuid.uuid4().hex[:12]}"
    aria = html.escape(f"Full run identifier: {raw_run_id}", quote=True)
    return (
        f'<span class="tx-run-id-info" data-testid="tx-run-id-info">'
        f'<button type="button" class="tx-run-id-info-btn" tabindex="0" '
        f'aria-label="{aria}" aria-describedby="{tip_id}">ⓘ</button>'
        f'<span id="{tip_id}" class="tx-run-id-info-tip" role="tooltip">'
        f"{escaped_id}</span>"
        f"</span>"
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
