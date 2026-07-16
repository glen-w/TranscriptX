"""Shared main-content width control for the Streamlit GUI."""

from __future__ import annotations

import streamlit as st

from transcriptx.web.navigation import PAGE_SPECS

# Canonical PAGE_SPECS keys that need near-full usable width.
WIDE_PAGE_KEYS: frozenset[str] = frozenset(
    {"Charts", "Transcript", "Artifacts", "Home"}
)

_CONSTRAINED_CSS = """
<style>
/* tx-page-layout: constrained — complete rule for this rerun */
section[data-testid="stAppViewContainer"] .block-container {
    max-width: 1240px;
    margin-left: auto;
    margin-right: auto;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
}
</style>
"""

_WIDE_CSS = """
<style>
/* tx-page-layout: wide — complete rule for this rerun */
section[data-testid="stAppViewContainer"] .block-container {
    max-width: min(100%, 1600px);
    margin-left: auto;
    margin-right: auto;
    padding-left: 1.5rem;
    padding-right: 1.5rem;
}
</style>
"""


def page_uses_wide_layout(page_key: str | None) -> bool:
    """Return True when ``page_key`` is an intentionally wide page."""
    return bool(page_key) and page_key in WIDE_PAGE_KEYS


def assert_wide_pages_registered() -> None:
    """Raise if any wide-page key is missing from PAGE_SPECS."""
    registered = {spec.key for spec in PAGE_SPECS}
    missing = WIDE_PAGE_KEYS - registered
    if missing:
        raise AssertionError(
            f"Wide page keys missing from PAGE_SPECS: {sorted(missing)}"
        )


def apply_page_layout(*, wide: bool) -> None:
    """Inject one complete width rule for the current rerun.

    Must run after ``inject_global_styles()`` so this declaration wins over any
    base ``.block-container`` styling. Emits a full rule each time so a normal
    page after a wide page restores the constrained width.
    """
    st.markdown(_WIDE_CSS if wide else _CONSTRAINED_CSS, unsafe_allow_html=True)
