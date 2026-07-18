"""Contract: action-link pipe separators live on columns, not button ::after."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_action_link_separators_use_column_after_not_button() -> None:
    shell_path = (
        Path(__file__).resolve().parents[2] / "src" / "transcriptx" / "web" / "shell.py"
    )
    source = shell_path.read_text(encoding="utf-8")
    assert 'st-key-tx_al_"' in source or "st-key-tx_al_" in source
    assert '[data-testid="stColumn"]:not(:last-child)::after' in source
    # Regression guard: separators must not be painted on button ::after
    # (Streamlit tertiary buttons clip/override that pseudo-element).
    assert 'stButton"] > button::after' not in source
    assert 'stDownloadButton"] > button::after' not in source
