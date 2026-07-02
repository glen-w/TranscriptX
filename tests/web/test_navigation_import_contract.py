"""Ensure navigation.py does not eagerly import page modules."""

from __future__ import annotations

from pathlib import Path


def test_navigation_has_no_module_level_page_modules_imports() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "transcriptx"
        / "web"
        / "navigation.py"
    ).read_text(encoding="utf-8")
    for line in source.splitlines():
        if not line or line[0].isspace():
            continue
        if "page_modules" in line:
            raise AssertionError(
                f"module-level page_modules import not allowed: {line.strip()}"
            )
