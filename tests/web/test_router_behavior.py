"""Tests for router behavior."""

from __future__ import annotations

import transcriptx.web.router as router


def test_route_current_page_unknown_page_warns_and_home(monkeypatch) -> None:
    calls = {"warn": 0, "home": 0}
    monkeypatch.setattr(router, "context_readiness", lambda _s: {})
    monkeypatch.setattr(
        router,
        "evaluate_page_access",
        lambda _page, _prereq, _ready: type("A", (), {"allowed": True})(),
    )
    monkeypatch.setattr(router.st, "warning", lambda _msg: calls.__setitem__("warn", 1))
    monkeypatch.setattr(router, "_render_home", lambda: calls.__setitem__("home", 1))
    monkeypatch.setattr(router, "build_page_renderers", lambda **_kwargs: {})

    router.route_current_page(
        {"page": "Unknown"},
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    assert calls == {"warn": 1, "home": 1}


def test_route_current_page_inaccessible_falls_back(monkeypatch) -> None:
    called = {"home": 0}
    monkeypatch.setattr(router, "context_readiness", lambda _s: {})
    monkeypatch.setattr(
        router,
        "evaluate_page_access",
        lambda _page, _prereq, _ready: type("A", (), {"allowed": False})(),
    )
    monkeypatch.setattr(router, "fallback_for_page", lambda _p: "Home")
    monkeypatch.setattr(
        router,
        "build_page_renderers",
        lambda **_kwargs: {"Home": lambda: called.__setitem__("home", 1)},
    )
    router.route_current_page(
        {"page": "Charts"},
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    assert called["home"] == 1


def test_route_current_page_accessible_calls_renderer(monkeypatch) -> None:
    called = {"home": 0}
    monkeypatch.setattr(router, "context_readiness", lambda _s: {})
    monkeypatch.setattr(
        router,
        "evaluate_page_access",
        lambda _page, _prereq, _ready: type("A", (), {"allowed": True})(),
    )
    monkeypatch.setattr(
        router,
        "build_page_renderers",
        lambda **_kwargs: {"Home": lambda: called.__setitem__("home", 1)},
    )
    router.route_current_page(
        {"page": "Home"},
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    assert called["home"] == 1


def test_route_current_page_missing_page_key_defaults_home(monkeypatch) -> None:
    called = {"home": 0}
    monkeypatch.setattr(router, "context_readiness", lambda _s: {})
    monkeypatch.setattr(
        router,
        "evaluate_page_access",
        lambda _page, _prereq, _ready: type("A", (), {"allowed": True})(),
    )
    monkeypatch.setattr(
        router,
        "build_page_renderers",
        lambda **_kwargs: {"Home": lambda: called.__setitem__("home", 1)},
    )
    router.route_current_page(
        {},
        corrections_studio_available=False,
        render_corrections_studio=None,
    )
    assert called["home"] == 1
