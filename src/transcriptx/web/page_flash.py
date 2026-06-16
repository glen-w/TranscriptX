"""One-shot page flash renderer."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.state import PAGE_FLASH_KIND, PAGE_FLASH_MESSAGE, try_page_toast


def consume_page_flash() -> None:
    """Show one-shot flash banner and optional toast; clear keys."""
    if PAGE_FLASH_MESSAGE not in st.session_state:
        return
    msg = st.session_state.pop(PAGE_FLASH_MESSAGE, "")
    kind = st.session_state.pop(PAGE_FLASH_KIND, "info")
    if not msg:
        return
    if kind == "success":
        st.success(msg)
    elif kind == "warning":
        st.warning(msg)
    elif kind == "error":
        st.error(msg)
    else:
        st.info(msg)
    try_page_toast(msg)
