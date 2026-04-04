"""Taxonomy-based empty states with at most two navigation CTAs."""

from __future__ import annotations

import html
from typing import Literal

import streamlit as st

EmptyKind = Literal[
    "missing_prerequisite",
    "no_results_yet",
    "filtered_to_zero",
    "module_unavailable",
    "error_degraded",
]


def render_empty_state(
    kind: EmptyKind,
    headline: str,
    detail: str,
    primary_action: tuple[str, str] | None = None,
    secondary_action: tuple[str, str] | None = None,
) -> None:
    """
    primary_action / secondary_action: (button_label, target_page_key).
    """
    hero = kind == "missing_prerequisite"
    hero_cls = " tx-empty-hero" if hero else ""
    st.markdown(
        f'<div class="tx-empty tx-empty-{html.escape(kind)}{hero_cls}">'
        f"<h4>{html.escape(headline)}</h4>"
        f"<p>{html.escape(detail)}</p></div>",
        unsafe_allow_html=True,
    )
    cols = st.columns([2, 2, 3])
    if primary_action:
        label, page = primary_action
        with cols[0]:
            if st.button(
                label,
                type="primary",
                key=f"empty_pri_{kind}_{label}"[:64],
            ):
                st.session_state["page"] = page
                st.rerun()
    if secondary_action:
        label, page = secondary_action
        with cols[1]:
            if st.button(label, key=f"empty_sec_{kind}_{label}"[:64]):
                st.session_state["page"] = page
                st.rerun()
