"""Ask nav: hidden when RAG is off; one-transcript scope."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.rag.flags import rag_enabled_from_env
from transcriptx.web.navigation import PAGE_SPECS
from transcriptx.web.sidebar import _ask_nav_enabled


def test_ask_page_requires_run_scoped_not_group() -> None:
    ask = next(spec for spec in PAGE_SPECS if spec.key == "Ask")
    assert ask.required_context == "run_scoped"


def test_ask_nav_hidden_when_flag_off(monkeypatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_RAG_ENABLED", raising=False)
    assert rag_enabled_from_env() is False
    assert _ask_nav_enabled() is False
    monkeypatch.setenv("TRANSCRIPTX_RAG_ENABLED", "true")
    assert _ask_nav_enabled() is True


def test_sidebar_skips_ask_when_flag_off() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "transcriptx"
        / "web"
        / "sidebar.py"
    ).read_text(encoding="utf-8")
    assert 'spec.key == "Ask"' in source
    assert "_ask_nav_enabled" in source


def test_ask_page_has_index_button_not_settings() -> None:
    source = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "transcriptx"
        / "web"
        / "page_modules"
        / "ask.py"
    ).read_text(encoding="utf-8")
    assert "Index this transcript" in source
    assert "Build RAG Index" not in source
    assert "Settings →" not in source
