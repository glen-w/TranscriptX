"""Guardrails for sidebar Streamlit API usage."""

from __future__ import annotations

import inspect
from pathlib import Path

import streamlit as st


def _sidebar_source() -> str:
    return (
        Path(__file__).resolve().parents[2]
        / "src"
        / "transcriptx"
        / "web"
        / "sidebar.py"
    ).read_text(encoding="utf-8")


def test_sidebar_does_not_use_st_expander() -> None:
    assert "st.expander" not in _sidebar_source()


def test_sidebar_does_not_use_st_toggle() -> None:
    source = _sidebar_source()
    assert "st.toggle" not in source
    assert "_sidebar_section" not in source


def test_sidebar_has_no_tx_nav_state_keys() -> None:
    source = _sidebar_source()
    assert "TX_NAV_" not in source


def test_sidebar_uses_static_nav_sections() -> None:
    source = _sidebar_source()
    assert "_nav_section" in source
    assert "pages_in_section" in source


def test_streamlit_expander_key_support_is_version_dependent() -> None:
    """Document dynamic expander availability; sidebar avoids keyed expanders either way."""
    sig = inspect.signature(st.expander)
    has_key = "key" in sig.parameters
    has_on_change = "on_change" in sig.parameters
    assert has_key == has_on_change
