"""Patch Streamlit (and other names) on every Speakers UI module."""

from __future__ import annotations

import importlib
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

SPEAKERS_UI_MODULES = (
    "transcriptx.web.page_modules.speakers",
    "transcriptx.web.ui.speakers.support",
    "transcriptx.web.ui.speakers.directory",
    "transcriptx.web.ui.speakers.detail",
    "transcriptx.web.ui.speakers.charts",
    "transcriptx.web.ui.speakers.forms",
)


def speakers_ui_paths() -> list[Path]:
    root = Path(__file__).resolve().parents[2]
    return [
        root / "src" / "transcriptx" / "web" / "page_modules" / "speakers.py",
        *sorted(
            (root / "src" / "transcriptx" / "web" / "ui" / "speakers").glob("*.py")
        ),
    ]


def speakers_ui_source() -> str:
    """Concatenated Speakers UI sources for string-contract tests."""
    return "\n".join(p.read_text(encoding="utf-8") for p in speakers_ui_paths())


def patch_speakers_attr(monkeypatch, name: str, value) -> None:
    for modname in SPEAKERS_UI_MODULES:
        mod = importlib.import_module(modname)
        if hasattr(mod, name):
            monkeypatch.setattr(mod, name, value)


@contextmanager
def patch_speakers_object(name: str, value) -> Iterator[None]:
    with ExitStack() as stack:
        for modname in SPEAKERS_UI_MODULES:
            mod = importlib.import_module(modname)
            if hasattr(mod, name):
                stack.enter_context(patch.object(mod, name, value))
        yield
