"""Presentation visibility helpers (separate from page access prerequisites)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from transcriptx.web.navigation import (
    NavSection,
    PageSpec,
    get_page_spec,
    pages_in_section,
)
from transcriptx.web.presentation.prefs import MODE_FULL, MODE_GUIDED, PresentationMode
from transcriptx.web.presentation.resolve import MODE_LABELS, set_presentation_mode

if TYPE_CHECKING:
    pass

FULL_ONLY_PAGE_KEYS: frozenset[str] = frozenset(
    {
        "Audio Prep",
        "Audio Merge",
        "Corrections Studio",
        "Speaker ID",
        "Performance",
        "Profiles",
        "Dashboard Builder",
        "Diagnostics",
    }
)

# Settings hub tabs visible under Guided (switch lives above tabs).
GUIDED_SETTINGS_TABS: tuple[str, ...] = (
    "Configuration",
    "Analysis",
    "Storage",
    "Speakers",
)

FULL_SETTINGS_TABS: tuple[str, ...] = GUIDED_SETTINGS_TABS + (
    "Interface",
    "Models",
    "Questions",
)


def page_visible_in_presentation(
    spec: PageSpec | str,
    mode: PresentationMode,
) -> bool:
    if mode == MODE_FULL:
        return True
    if isinstance(spec, PageSpec):
        if spec.presentation == "full_only":
            return False
        return spec.key not in FULL_ONLY_PAGE_KEYS
    return str(spec) not in FULL_ONLY_PAGE_KEYS


def visible_pages_in_section(
    section: NavSection,
    mode: PresentationMode,
) -> list[PageSpec]:
    """Filter ``pages_in_section`` by presentation without changing its contract."""
    return [
        spec
        for spec in pages_in_section(section)
        if page_visible_in_presentation(spec, mode)
    ]


def render_full_only_unlock_banner(page_key: str) -> None:
    """Banner-only UI for deep-linked Full-only pages under Guided."""
    import streamlit as st

    label = get_page_spec(page_key).label
    st.warning(
        f"**{label}** is available in {MODE_LABELS[MODE_FULL]}. "
        f"You are currently in {MODE_LABELS[MODE_GUIDED]}."
    )
    st.caption(
        "Switching reveals specialist tools and advanced settings. "
        "Your analysis selections and saved configuration are not changed."
    )
    if st.button(
        f"Switch to {MODE_LABELS[MODE_FULL]}",
        type="primary",
        key="presentation_unlock_full",
    ):
        result = set_presentation_mode(MODE_FULL)
        if result.ok:
            st.rerun()
        elif result.error:
            st.error(result.error)
