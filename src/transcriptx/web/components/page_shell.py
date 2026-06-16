"""Reusable page header: title, description, badges, nav-only actions.

Page help text lives in ``render_page_help`` (below main content), not here.
"""

from __future__ import annotations

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
        parts = "".join(f'<span class="tx-badge">{b}</span>' for b in badges if b)
        badge_html = f'<div style="margin:0.35rem 0 0.5rem 0;">{parts}</div>'

    st.markdown(
        f'<div class="tx-page-shell-title">{title}</div>' f"{badge_html}",
        unsafe_allow_html=True,
    )
    if description:
        st.markdown(
            f'<p class="tx-page-shell-desc">{description}</p>',
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


def render_page_help(help_md: str | None, key_suffix: str = "") -> None:
    """Render collapsed page-level help below main content.

    No-op when ``help_md`` is falsy. Wrapped in the ``.tx-page-help`` container so
    the shared CSS in ``shell.py`` styles the expander more quietly than body text.
    """
    if not help_md:
        return

    st.markdown('<div class="tx-page-help">', unsafe_allow_html=True)
    try:
        if key_suffix:
            expander = st.expander(
                "About this page",
                expanded=False,
                key=f"page_help{key_suffix}",  # type: ignore[call-arg]
            )
        else:
            expander = st.expander("About this page", expanded=False)
    except TypeError:
        # Older Streamlit builds do not accept ``key`` on st.expander.
        expander = st.expander("About this page", expanded=False)
    with expander:
        st.markdown(help_md)
    st.markdown("</div>", unsafe_allow_html=True)
