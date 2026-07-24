"""Guard against empty markdown wrappers painting thick white bars."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_WEB_ROOT = Path(__file__).resolve().parents[2] / "src" / "transcriptx" / "web"
_SHELL_PATH = _WEB_ROOT / "shell.py"

# Open-only wrapper divs that Streamlit cannot nest widgets inside; they render
# as empty blocks. White / near-opaque light backgrounds become thick bars on
# dark chrome.
_EMPTY_WRAPPER_OPEN = re.compile(
    r"""st\.markdown\(\s*['"]<div\s+class=["']([^"']+)["']>\s*['"]""",
    re.MULTILINE,
)
_CLASS_RULE = re.compile(
    r"\.([A-Za-z0-9_-]+)\s*\{([^}]*)\}",
    re.MULTILINE,
)
_WHITE_BG = re.compile(
    r"background(?:-color)?\s*:\s*"
    r"(?:#fff(?:fff)?\b|white\b|rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*"
    r"(?:0\.(?:[5-9]\d*|99)|1(?:\.0+)?)\s*\))",
    re.IGNORECASE,
)


@pytest.mark.unit
def test_shell_css_drops_transcript_controls_white_bar() -> None:
    source = _SHELL_PATH.read_text(encoding="utf-8")
    assert ".tx-transcript-controls" not in source


@pytest.mark.unit
def test_empty_markdown_wrapper_classes_have_no_white_background() -> None:
    """Empty open/close ``st.markdown`` div wrappers must not use white fills."""
    wrapper_classes: set[str] = set()
    for path in _WEB_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        wrapper_classes.update(_EMPTY_WRAPPER_OPEN.findall(text))

    shell_css = _SHELL_PATH.read_text(encoding="utf-8")
    class_rules = {
        name: body
        for name, body in _CLASS_RULE.findall(shell_css)
        if name in wrapper_classes
    }

    white_bar_classes = sorted(
        name for name, body in class_rules.items() if _WHITE_BG.search(body)
    )
    assert white_bar_classes == [], (
        "Empty Streamlit markdown wrappers cannot contain widgets; a white "
        f"background paints a thick bar on dark UI: {white_bar_classes}"
    )
