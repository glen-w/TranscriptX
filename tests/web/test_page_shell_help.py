"""Tests for render_page_help rendering behavior (mocked Streamlit)."""

from __future__ import annotations

from contextlib import contextmanager

import transcriptx.web.components.page_shell as page_shell


class _FakeSt:
    def __init__(self):
        self.markdown_calls: list[str] = []
        self.expander_calls: list[tuple[str, dict]] = []
        self.expander_entered = 0

    def markdown(self, body, **kwargs):
        self.markdown_calls.append(body)

    @contextmanager
    def _expander_cm(self):
        self.expander_entered += 1
        yield

    def expander(self, label, **kwargs):
        self.expander_calls.append((label, kwargs))
        return self._expander_cm()


def test_render_page_help_noop_when_none(monkeypatch):
    fake = _FakeSt()
    monkeypatch.setattr(page_shell, "st", fake)
    page_shell.render_page_help(None)
    assert fake.markdown_calls == []
    assert fake.expander_calls == []


def test_render_page_help_noop_when_empty(monkeypatch):
    fake = _FakeSt()
    monkeypatch.setattr(page_shell, "st", fake)
    page_shell.render_page_help("")
    assert fake.expander_calls == []


def test_render_page_help_renders_expander_and_markdown(monkeypatch):
    fake = _FakeSt()
    monkeypatch.setattr(page_shell, "st", fake)
    page_shell.render_page_help("**Help body**")

    assert len(fake.expander_calls) == 1
    label, _kwargs = fake.expander_calls[0]
    assert label == "About this page"
    assert fake.expander_entered == 1
    # Help text rendered inside the expander, plus the .tx-page-help wrapper markup.
    assert "**Help body**" in fake.markdown_calls
    assert any("tx-page-help" in m for m in fake.markdown_calls)


def test_render_page_help_uses_key_suffix(monkeypatch):
    fake = _FakeSt()
    monkeypatch.setattr(page_shell, "st", fake)
    page_shell.render_page_help("body", key_suffix="_charts")

    assert len(fake.expander_calls) == 1
    _label, kwargs = fake.expander_calls[0]
    assert kwargs.get("key") == "page_help_charts"
