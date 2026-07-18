"""Overview page thin Streamlit orchestration contracts (L3)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.web.components.run_scoped_page import RunScopedPageContext
from tests.web.streamlit_doubles import DummyHomeStreamlit


@pytest.mark.unit
def test_overview_missing_context_uses_run_scoped_guard(monkeypatch) -> None:
    import transcriptx.web.page_modules.overview as mod

    guard_calls: list = []
    monkeypatch.setattr(mod, "register_builtin_blocks", lambda: None)
    monkeypatch.setattr(
        mod,
        "render_run_scoped_page",
        lambda config, render_body=None, **_k: guard_calls.append(config) or False,
    )

    mod.render_overview()

    assert guard_calls
    assert guard_calls[0].title == "Overview"
    assert "Select a subject" in guard_calls[0].empty_headline


@pytest.mark.unit
def test_overview_body_empty_artifacts(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.web.page_modules.overview as mod

    empty_calls: list = []
    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "render_empty_state",
        lambda *args, **kwargs: empty_calls.append((args, kwargs)),
    )
    monkeypatch.setattr(
        mod,
        "build_artifact_index",
        lambda *_a, **_k: SimpleNamespace(entries=[]),
    )
    frag_calls: list = []
    monkeypatch.setattr(
        mod, "_overview_blocks_fragment", lambda *_a, **_k: frag_calls.append(True)
    )

    ctx = RunScopedPageContext(
        subject=SimpleNamespace(
            subject_type="transcript", subject_id="s1", scope="transcript"
        ),
        run_id="20260101_120000",
        run_root=tmp_path,
    )
    mod._render_overview_body(ctx)

    assert empty_calls
    assert "No artifacts" in empty_calls[0][0][1]
    assert frag_calls == []


@pytest.mark.unit
def test_overview_body_invokes_blocks_fragment(monkeypatch, tmp_path: Path) -> None:
    import transcriptx.web.page_modules.overview as mod

    DummyHomeStreamlit.session_state = {}
    frag_calls: list = []
    layout = SimpleNamespace(pages={"overview": SimpleNamespace(blocks=[])})
    session_ctx = SimpleNamespace()

    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)
    monkeypatch.setattr(mod, "render_page_shell", lambda *_a, **_k: None)
    monkeypatch.setattr(
        mod,
        "build_artifact_index",
        lambda *_a, **_k: SimpleNamespace(entries=[SimpleNamespace()]),
    )
    monkeypatch.setattr(mod, "build_context_from_session", lambda _ss: session_ctx)
    monkeypatch.setattr(mod, "load_active_layout", lambda _ss: layout)
    monkeypatch.setattr(
        mod,
        "_overview_blocks_fragment",
        lambda ctx, lay: frag_calls.append((ctx, lay)),
    )

    ctx = RunScopedPageContext(
        subject=SimpleNamespace(
            subject_type="transcript", subject_id="s1", scope="transcript"
        ),
        run_id="20260101_120000",
        run_root=tmp_path,
    )
    mod._render_overview_body(ctx)

    assert frag_calls == [(session_ctx, layout)]
