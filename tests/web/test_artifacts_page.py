"""Artifacts page Preview vs Browse section routing (L3)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.web.components.run_scoped_page import RunScopedPageContext
from transcriptx.web.state import ARTIFACTS_KEY_SECTION
from tests.web.streamlit_doubles import DummyHomeStreamlit


@pytest.mark.unit
def test_artifacts_body_browse_section(monkeypatch) -> None:
    import transcriptx.web.page_modules.artifacts as mod

    DummyHomeStreamlit.session_state = {ARTIFACTS_KEY_SECTION: "Browse"}
    browse_calls: list = []
    preview_calls: list = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def segmented_control(*_a, **_k):
            raise RuntimeError("force radio fallback")

        @staticmethod
        def radio(_label, options, index=0, **_kwargs):
            return options[index]

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "reconcile_artifact_selection", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_render_browse", lambda ctx: browse_calls.append(ctx))
    monkeypatch.setattr(mod, "_render_preview", lambda ctx: preview_calls.append(ctx))
    monkeypatch.setattr(mod, "_render_export", lambda *_a, **_k: None)

    ctx = RunScopedPageContext(
        subject=SimpleNamespace(subject_type="transcript", subject_id="s1"),
        run_id="r1",
        run_root=MagicMock(),
    )
    mod._render_artifacts_body(ctx)

    assert browse_calls
    assert preview_calls == []
    assert DummyHomeStreamlit.session_state[ARTIFACTS_KEY_SECTION] == "Browse"


@pytest.mark.unit
def test_artifacts_body_preview_section(monkeypatch) -> None:
    import transcriptx.web.page_modules.artifacts as mod

    DummyHomeStreamlit.session_state = {ARTIFACTS_KEY_SECTION: "Preview"}
    browse_calls: list = []
    preview_calls: list = []

    class _St(DummyHomeStreamlit):
        @staticmethod
        def segmented_control(*_a, **_k):
            raise RuntimeError("force radio fallback")

        @staticmethod
        def radio(_label, options, index=0, **_kwargs):
            return "Preview"

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "reconcile_artifact_selection", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "_render_browse", lambda ctx: browse_calls.append(ctx))
    monkeypatch.setattr(mod, "_render_preview", lambda ctx: preview_calls.append(ctx))
    monkeypatch.setattr(mod, "_render_export", lambda *_a, **_k: None)

    ctx = RunScopedPageContext(
        subject=SimpleNamespace(subject_type="transcript", subject_id="s1"),
        run_id="r1",
        run_root=MagicMock(),
    )
    mod._render_artifacts_body(ctx)

    assert preview_calls
    assert browse_calls == []
    assert DummyHomeStreamlit.session_state[ARTIFACTS_KEY_SECTION] == "Preview"


@pytest.mark.unit
def test_render_artifacts_uses_run_scoped_guard(monkeypatch) -> None:
    import transcriptx.web.page_modules.artifacts as mod

    calls: list = []
    monkeypatch.setattr(
        mod,
        "render_run_scoped_page",
        lambda config, render_body=None, **_k: calls.append(config) or False,
    )

    mod.render_artifacts()

    assert calls
    assert calls[0].title == "Artifacts"
