"""Insights page thin Streamlit orchestration contracts (L3)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.web.components.run_scoped_page import RunScopedPageContext
from tests.web.streamlit_doubles import DummyHomeStreamlit


@pytest.mark.unit
def test_insights_missing_context_uses_run_scoped_guard(monkeypatch) -> None:
    import transcriptx.web.page_modules.insights as mod

    guard_calls: list = []
    monkeypatch.setattr(mod, "register_builtin_blocks", lambda: None)
    monkeypatch.setattr(
        mod,
        "render_run_scoped_page",
        lambda config, render_body=None, **_k: guard_calls.append(config) or False,
    )

    mod.render_insights()

    assert guard_calls
    assert guard_calls[0].title == "Insights"
    assert guard_calls[0].empty_headline == "Select a subject and run"


@pytest.mark.unit
def test_insights_body_invokes_sections_fragment(monkeypatch) -> None:
    import transcriptx.web.page_modules.insights as mod

    DummyHomeStreamlit.session_state = {"run_id": "r1"}
    frag_calls: list = []
    layout = SimpleNamespace(pages={"insights": SimpleNamespace(blocks=[])})
    block_ctx = SimpleNamespace()

    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "build_context_from_session", lambda _ss: block_ctx)
    monkeypatch.setattr(mod, "load_active_layout", lambda _ss: layout)
    monkeypatch.setattr(
        mod,
        "_insights_sections_fragment",
        lambda ctx, lay: frag_calls.append((ctx, lay)),
    )

    ctx = RunScopedPageContext(
        subject=SimpleNamespace(subject_type="transcript", subject_id="s1"),
        run_id="r1",
        run_root=MagicMock(),
    )
    mod._render_insights_body(ctx)

    assert frag_calls == [(block_ctx, layout)]
