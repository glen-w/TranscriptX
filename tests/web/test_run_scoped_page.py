"""Tests for run scoped page."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.web.components.run_scoped_page import (
    RunScopedPageConfig,
    RunScopedPageContext,
    render_run_scoped_page,
)
from tests.web.streamlit_doubles import DummyStreamlit

_CONFIG = RunScopedPageConfig(
    title="Test Page",
    description="Test description",
    empty_headline="Select a subject and run",
    empty_detail="Use the sidebar.",
    primary_action=("Open Library", "Library"),
    secondary_action=("Run Analysis", "Run Analysis"),
)


@pytest.fixture
def st_double(monkeypatch):
    dummy = DummyStreamlit()
    dummy.session_state = {}
    captured: dict = {}
    import transcriptx.web.components.run_scoped_page as mod

    monkeypatch.setattr(mod, "st", dummy)
    monkeypatch.setattr(
        mod,
        "render_page_shell",
        lambda *args, **kwargs: captured.setdefault("shell", (args, kwargs)),
    )
    monkeypatch.setattr(
        mod,
        "render_empty_state",
        lambda *args, **kwargs: captured.setdefault("empty", (args, kwargs)),
    )
    return mod, dummy, captured


def test_missing_subject_renders_prereq_guard_and_skips_body(monkeypatch, st_double):
    mod, dummy, captured = st_double
    monkeypatch.setattr(mod.SubjectService, "resolve_current_subject", lambda _ss: None)
    body_calls: list[RunScopedPageContext] = []

    result = render_run_scoped_page(
        _CONFIG,
        render_body=lambda ctx: body_calls.append(ctx),
    )

    assert result is False
    assert body_calls == []
    assert captured["shell"][0][0] == "Test Page"
    assert captured["shell"][0][1] == "Test description"
    assert captured["empty"][0][0] == "missing_prerequisite"


def test_missing_run_id_renders_prereq_guard(monkeypatch, st_double):
    mod, dummy, captured = st_double
    subject = SimpleNamespace(
        scope=SimpleNamespace(scope_type="transcript"),
        subject_id="slug-1",
    )
    monkeypatch.setattr(
        mod.SubjectService, "resolve_current_subject", lambda _ss: subject
    )
    dummy.session_state["run_id"] = None
    body_calls: list[RunScopedPageContext] = []

    result = render_run_scoped_page(
        _CONFIG,
        render_body=lambda ctx: body_calls.append(ctx),
    )

    assert result is False
    assert body_calls == []
    assert "empty" in captured
    assert captured["shell"][0][1] == "Test description"


def test_missing_run_dir_shows_guard_when_configured(monkeypatch, st_double, tmp_path):
    mod, dummy, captured = st_double
    subject = SimpleNamespace(
        scope=SimpleNamespace(scope_type="transcript"),
        subject_id="slug-1",
    )
    missing_root = tmp_path / "missing_run"
    monkeypatch.setattr(
        mod.SubjectService, "resolve_current_subject", lambda _ss: subject
    )
    monkeypatch.setattr(
        mod.RunIndex,
        "get_run_root",
        lambda *_args, **_kwargs: missing_root,
    )
    dummy.session_state["run_id"] = "run-1"
    info_calls: list[str] = []
    monkeypatch.setattr(mod.st, "info", lambda msg: info_calls.append(msg))
    body_calls: list[RunScopedPageContext] = []

    result = render_run_scoped_page(
        _CONFIG,
        render_body=lambda ctx: body_calls.append(ctx),
        on_missing_run_dir="info",
    )

    assert result is False
    assert body_calls == []
    assert info_calls == ["Run folder not found."]
    assert "shell" in captured
    assert captured["shell"][0][1] == "Test description"


def test_happy_path_calls_body_with_context(monkeypatch, st_double, tmp_path):
    mod, dummy, captured = st_double
    subject = SimpleNamespace(
        scope=SimpleNamespace(scope_type="transcript"),
        subject_id="slug-1",
    )
    run_root = tmp_path / "run-1"
    run_root.mkdir()
    monkeypatch.setattr(
        mod.SubjectService, "resolve_current_subject", lambda _ss: subject
    )
    monkeypatch.setattr(
        mod.RunIndex,
        "get_run_root",
        lambda *_args, **_kwargs: run_root,
    )
    dummy.session_state["run_id"] = "run-1"
    body_calls: list[RunScopedPageContext] = []

    result = render_run_scoped_page(
        _CONFIG,
        render_body=lambda ctx: body_calls.append(ctx),
    )

    assert result is True
    assert len(body_calls) == 1
    assert body_calls[0].run_id == "run-1"
    assert body_calls[0].run_root == run_root
    assert body_calls[0].subject is subject
    assert "empty" not in captured


def test_missing_run_dir_defaults_to_empty_state(monkeypatch, st_double, tmp_path):
    mod, dummy, captured = st_double
    subject = SimpleNamespace(
        scope=SimpleNamespace(scope_type="transcript"),
        subject_id="slug-1",
    )
    missing_root = tmp_path / "missing_run"
    monkeypatch.setattr(
        mod.SubjectService, "resolve_current_subject", lambda _ss: subject
    )
    monkeypatch.setattr(
        mod.RunIndex,
        "get_run_root",
        lambda *_args, **_kwargs: missing_root,
    )
    dummy.session_state["run_id"] = "run-1"
    body_calls: list[RunScopedPageContext] = []

    result = render_run_scoped_page(
        _CONFIG,
        render_body=lambda ctx: body_calls.append(ctx),
    )

    assert result is False
    assert body_calls == []
    assert captured["empty"][0][0] == "error_degraded"


def test_missing_run_dir_none_escape_hatch_calls_body(monkeypatch, st_double, tmp_path):
    mod, dummy, captured = st_double
    subject = SimpleNamespace(
        scope=SimpleNamespace(scope_type="transcript"),
        subject_id="slug-1",
    )
    missing_root = tmp_path / "missing_run"
    monkeypatch.setattr(
        mod.SubjectService, "resolve_current_subject", lambda _ss: subject
    )
    monkeypatch.setattr(
        mod.RunIndex,
        "get_run_root",
        lambda *_args, **_kwargs: missing_root,
    )
    dummy.session_state["run_id"] = "run-1"
    body_calls: list[RunScopedPageContext] = []

    result = render_run_scoped_page(
        _CONFIG,
        render_body=lambda ctx: body_calls.append(ctx),
        on_missing_run_dir=None,
    )

    assert result is True
    assert len(body_calls) == 1
    assert body_calls[0].run_root == missing_root
