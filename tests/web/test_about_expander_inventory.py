"""Repository guard: no About-this-page expanders in production web code."""

from __future__ import annotations

from pathlib import Path

WEB_ROOT = Path(__file__).resolve().parents[2] / "src" / "transcriptx" / "web"


def _iter_web_py_files():
    for path in WEB_ROOT.rglob("*.py"):
        yield path


def test_no_about_this_page_expanders_in_production_web():
    offenders: list[str] = []
    for path in _iter_web_py_files():
        text = path.read_text(encoding="utf-8")
        if "About this page" in text:
            offenders.append(str(path.relative_to(WEB_ROOT.parent.parent.parent)))
        if "tx-page-help" in text:
            offenders.append(str(path.relative_to(WEB_ROOT.parent.parent.parent)))
        if "render_page_help" in text:
            offenders.append(str(path.relative_to(WEB_ROOT.parent.parent.parent)))
    assert offenders == [], f"About-page remnants found: {offenders}"


def test_shell_has_no_tx_page_help_css():
    shell = (WEB_ROOT / "shell.py").read_text(encoding="utf-8")
    assert "tx-page-help" not in shell
