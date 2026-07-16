"""Reusable page header: title, description, badges, nav-only actions.

Page descriptions are rendered once immediately beneath the title.
"""

from __future__ import annotations

import html
from collections.abc import Callable

import streamlit as st


def render_page_shell(
    title: str,
    description: str | None = None,
    badges: list[str] | None = None,
    actions: list[tuple[str, str]] | None = None,
    *,
    extra: Callable[[], None] | None = None,
) -> None:
    """
    actions: list of (label, target_page_key) — sets st.session_state['page'] and reruns.
    """
    badge_html = ""
    if badges:
        parts = "".join(
            f'<span class="tx-badge">{html.escape(b)}</span>' for b in badges if b
        )
        badge_html = f'<div style="margin:0.35rem 0 0.5rem 0;">{parts}</div>'

    st.markdown(
        f'<div class="tx-page-shell-title">{html.escape(title)}</div>{badge_html}',
        unsafe_allow_html=True,
    )
    if description:
        st.markdown(
            f'<p class="tx-page-shell-desc">{html.escape(description)}</p>',
            unsafe_allow_html=True,
        )

    if extra:
        extra()

    if actions:
        n = len(actions)
        btn_cols = st.columns(n)
        for i, (label, page_key) in enumerate(actions):
            with btn_cols[i]:
                if st.button(label, key=f"shell_act_{abs(hash(title))}_{i}"):
                    st.session_state["page"] = page_key
                    st.rerun()
