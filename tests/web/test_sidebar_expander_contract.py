"""Guardrails for sidebar Streamlit API usage."""

from __future__ import annotations

import inspect
from pathlib import Path

import streamlit as st


def test_sidebar_does_not_use_st_expander() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "transcriptx"
        / "web"
        / "sidebar.py"
    ).read_text(encoding="utf-8")
    assert "st.expander" not in source


def test_sidebar_uses_explicit_toggle_sections() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "transcriptx"
        / "web"
        / "sidebar.py"
    ).read_text(encoding="utf-8")
    assert "st.toggle" in source
    assert "_sidebar_section" in source


def test_streamlit_expander_key_support_is_version_dependent() -> None:
    """Document dynamic expander availability; sidebar avoids keyed expanders either way."""
    sig = inspect.signature(st.expander)
    has_key = "key" in sig.parameters
    has_on_change = "on_change" in sig.parameters
    assert has_key == has_on_change
