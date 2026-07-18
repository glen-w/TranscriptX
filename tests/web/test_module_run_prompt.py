"""Fixed Run Analysis CTA under module-required empty hints."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.web.action_menus.services import PAGE_RUN_ANALYSIS
from transcriptx.web.blocks.context import build_block_context
from transcriptx.web.components.action_links import ACTION_LINK_KEY_PREFIX
from transcriptx.web.state import PAGE_KEY
from tests.web.streamlit_doubles import DummyHomeStreamlit


@pytest.fixture
def transcript_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    transcript = tmp_path / "call1.json"
    transcript.write_text('{"segments": []}', encoding="utf-8")
    other = tmp_path / "other.json"
    other.write_text('{"segments": []}', encoding="utf-8")
    run_dir = tmp_path / "slug" / "run-1"
    run_dir.mkdir(parents=True)

    from transcriptx.web.services.subject_service import SubjectService

    monkeypatch.setattr(
        SubjectService,
        "current_transcript_path",
        staticmethod(lambda _ss: str(transcript)),
    )
    return SimpleNamespace(
        transcript=transcript,
        other=other,
        slug="slug",
        run_dir=run_dir,
    )


@pytest.mark.unit
def test_identity_for_run_analysis_from_block_context(transcript_env) -> None:
    from transcriptx.web.components.module_run_prompt import identity_for_run_analysis

    ctx = build_block_context(
        run_root=transcript_env.run_dir,
        subject_type="transcript",
        subject_id=transcript_env.slug,
        run_id=transcript_env.run_dir.name,
        session_name=f"{transcript_env.slug}/{transcript_env.run_dir.name}",
        artifacts=[],
        run_results=None,
        layout_profile_id="default",
    )
    ss = {
        "subject_type": "transcript",
        "subject_id": transcript_env.slug,
        "run_id": transcript_env.run_dir.name,
    }
    identity = identity_for_run_analysis(ctx, session_state=ss)
    assert identity is not None
    assert identity.subject_type == "transcript"
    assert identity.subject_id == transcript_env.slug
    assert identity.transcript_path == transcript_env.transcript
    assert identity.run_id == transcript_env.run_dir.name


@pytest.mark.unit
def test_render_module_required_hint_navigates_with_identity(
    monkeypatch: pytest.MonkeyPatch, transcript_env
) -> None:
    import transcriptx.web.components.module_run_prompt as mod

    nav_calls: list = []
    info_msgs: list[str] = []
    pressed_key = f"{ACTION_LINK_KEY_PREFIX}mod_req_insights_empty"

    class _St(DummyHomeStreamlit):
        session_state = {
            "subject_type": "transcript",
            "subject_id": transcript_env.slug,
            "run_id": transcript_env.run_dir.name,
        }

        @staticmethod
        def info(msg, **_kwargs):
            info_msgs.append(msg)

        @classmethod
        def button(cls, _label, key=None, **_kwargs):
            return key == pressed_key

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        mod,
        "navigate_with_identity",
        lambda identity, page, session_state=None: nav_calls.append(
            (identity, page, session_state)
        ),
    )
    monkeypatch.setattr(mod, "render_action_link", lambda label, *, key, **_k: True)

    ctx = build_block_context(
        run_root=transcript_env.run_dir,
        subject_type="transcript",
        subject_id=transcript_env.slug,
        run_id=transcript_env.run_dir.name,
        session_name=None,
        artifacts=[],
        run_results=None,
        layout_profile_id="default",
    )
    mod.render_module_required_hint(
        "Run the `insights` module to populate this view.",
        key="insights_empty",
        ctx=ctx,
    )

    assert info_msgs == ["Run the `insights` module to populate this view."]
    assert len(nav_calls) == 1
    identity, page, _ss = nav_calls[0]
    assert page == PAGE_RUN_ANALYSIS
    assert identity.subject_id == transcript_env.slug
    assert identity.transcript_path == transcript_env.transcript


@pytest.mark.unit
def test_render_module_required_hint_falls_back_without_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import transcriptx.web.components.module_run_prompt as mod

    class _St(DummyHomeStreamlit):
        session_state: dict = {}

        @staticmethod
        def info(*_a, **_k):
            return None

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(mod, "render_action_link", lambda *_a, **_k: True)
    monkeypatch.setattr(
        mod,
        "identity_for_run_analysis",
        lambda *_a, **_k: None,
    )

    mod.render_module_required_hint("Run the `summary` module.", key="summary_empty")

    assert _St.session_state[PAGE_KEY] == PAGE_RUN_ANALYSIS


@pytest.mark.unit
def test_insights_empty_uses_module_required_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import transcriptx.web.blocks.implementations.insights as mod

    hint_calls: list = []
    ctx = build_block_context(
        run_root=MagicMock(),
        subject_type="transcript",
        subject_id="slug",
        run_id="run-1",
        session_name=None,
        artifacts=[],
        run_results=None,
        layout_profile_id="default",
    )
    # Loader present but no insights payload.
    loader = MagicMock()
    loader.load_json.return_value = None
    monkeypatch.setattr(mod, "_loader", lambda _ctx: loader)
    monkeypatch.setattr(mod, "st", DummyHomeStreamlit)
    monkeypatch.setattr(
        mod,
        "render_module_required_hint",
        lambda msg, *, key, ctx=None: hint_calls.append((msg, key, ctx)),
    )

    mod.render_insights_contract(ctx, MagicMock())

    assert hint_calls
    assert "insights" in hint_calls[0][0]
    assert hint_calls[0][2] is ctx
