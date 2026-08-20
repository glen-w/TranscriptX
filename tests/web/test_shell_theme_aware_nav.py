"""Sidebar nav / brand must adapt to Streamlit light and dark chrome."""

from __future__ import annotations

from pathlib import Path

import pytest

_SHELL_PATH = (
    Path(__file__).resolve().parents[2] / "src" / "transcriptx" / "web" / "shell.py"
)


@pytest.mark.unit
def test_sidebar_nav_buttons_use_theme_text_color() -> None:
    source = _SHELL_PATH.read_text(encoding="utf-8")
    assert 'button[kind="secondary"]' in source
    assert "var(--text-color" in source
    # Hardcoded near-white labels break light Streamlit chrome.
    assert "color: #d7dee8 !important" not in source
    assert "color: #f3f9fd !important" not in source


@pytest.mark.unit
def test_brand_logo_emits_both_chrome_variants() -> None:
    source = _SHELL_PATH.read_text(encoding="utf-8")
    assert "tx-logo-light-chrome" in source
    assert "tx-logo-dark-chrome" in source
    assert "__txBrandChromeSync" in source
    assert "data-tx-chrome" in source
