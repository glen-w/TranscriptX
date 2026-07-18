"""Tests for page shell description rendering (no About expanders)."""

from __future__ import annotations

from contextlib import contextmanager

import transcriptx.web.components.page_shell as page_shell
import transcriptx.web.components.run_scoped_page as run_scoped


class _FakeSt:
    def __init__(self):
        self.markdown_calls: list[str] = []
        self.expander_calls: list = []
        self.session_state: dict = {}

    def markdown(self, body, **_kwargs):
        self.markdown_calls.append(body)

    def button(self, *_args, **_kwargs):
        return False

    def columns(self, n):
        return [self] * n

    def info(self, *_args, **_kwargs):
        return None

    def error(self, *_args, **_kwargs):
        return None

    @contextmanager
    def _noop(self):
        yield

    def expander(self, *args, **kwargs):
        self.expander_calls.append((args, kwargs))
        return self._noop()


def test_render_page_shell_description_below_title_once(monkeypatch):
    fake = _FakeSt()
    monkeypatch.setattr(page_shell, "st", fake)
    monkeypatch.setattr(page_shell, "consume_page_flash", lambda: None)
    page_shell.render_page_shell("Home", "Launchpad description.")
    assert any("tx-page-shell-title" in m and "Home" in m for m in fake.markdown_calls)
    desc_calls = [m for m in fake.markdown_calls if "tx-page-shell-desc" in m]
    assert len(desc_calls) == 1
    assert "Launchpad description." in desc_calls[0]
    assert fake.expander_calls == []


def test_render_page_shell_consumes_flash_after_description(monkeypatch):
    fake = _FakeSt()
    order: list[str] = []

    def _markdown(body, **_kwargs):
        fake.markdown_calls.append(body)
        if "tx-page-shell-title" in body:
            order.append("title")
        elif "tx-page-shell-desc" in body:
            order.append("description")

    fake.markdown = _markdown  # type: ignore[method-assign]
    monkeypatch.setattr(page_shell, "st", fake)
    monkeypatch.setattr(
        page_shell,
        "consume_page_flash",
        lambda: order.append("flash"),
    )
    page_shell.render_page_shell("Groups", "Manage groups.")
    assert order == ["title", "description", "flash"]


def test_render_page_help_removed():
    assert not hasattr(page_shell, "render_page_help")


def test_run_scoped_prereq_keeps_description(monkeypatch):
    fake = _FakeSt()
    monkeypatch.setattr(run_scoped, "st", fake)
    monkeypatch.setattr(page_shell, "st", fake)
    monkeypatch.setattr(
        run_scoped.SubjectService,
        "resolve_current_subject",
        staticmethod(lambda _ss: None),
    )
    empty_calls = []

    def _empty(*args, **kwargs):
        empty_calls.append(args)

    monkeypatch.setattr(run_scoped, "render_empty_state", _empty)
    monkeypatch.setattr(run_scoped, "render_page_shell", page_shell.render_page_shell)
    monkeypatch.setattr(page_shell, "consume_page_flash", lambda: None)

    cfg = run_scoped.RunScopedPageConfig(
        title="Overview",
        description="Visible description.",
        empty_headline="Select a subject and run",
        empty_detail="detail",
        primary_action=("Library", "Library"),
        secondary_action=("Run Analysis", "Run Analysis"),
    )
    assert (
        run_scoped.render_run_scoped_page(cfg, render_body=lambda _ctx: None) is False
    )
    desc_calls = [m for m in fake.markdown_calls if "tx-page-shell-desc" in m]
    assert len(desc_calls) == 1
    assert "Visible description." in desc_calls[0]
    assert empty_calls
    assert fake.expander_calls == []
