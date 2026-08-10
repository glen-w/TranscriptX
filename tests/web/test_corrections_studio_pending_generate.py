"""Corrections Studio UI: deferred generate / force orchestration contracts."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.web.streamlit_doubles import DummyColumn


class _RerunCalled(BaseException):
    """Stand-in for Streamlit stopping the script after st.rerun().

    Must not subclass Exception — start/generate handlers catch Exception.
    """


class _StudioStreamlit:
    session_state: dict = {}
    button_returns: dict[str, bool] = {}
    errors: list[str] = []
    infos: list[str] = []
    select_index: int = 1
    rerun_calls: int = 0

    @staticmethod
    def markdown(*_args, **_kwargs):
        return None

    @staticmethod
    def caption(*_args, **_kwargs):
        return None

    @staticmethod
    def success(*_args, **_kwargs):
        return None

    @staticmethod
    def warning(*_args, **_kwargs):
        return None

    @classmethod
    def info(cls, msg, **_kwargs):
        cls.infos.append(str(msg))
        return None

    @classmethod
    def error(cls, msg, **_kwargs):
        cls.errors.append(str(msg))
        return None

    @classmethod
    def selectbox(cls, *_args, **_kwargs):
        return cls.select_index

    @staticmethod
    def columns(_n):
        if isinstance(_n, int):
            return tuple(DummyColumn() for _ in range(_n))
        return tuple(DummyColumn() for _ in _n)

    @classmethod
    def button(cls, label, **_kwargs):
        return bool(cls.button_returns.get(label, False))

    @staticmethod
    def spinner(_msg):
        return DummyColumn()

    @classmethod
    def rerun(cls):
        cls.rerun_calls += 1
        raise _RerunCalled()


def _patch_studio(monkeypatch, mod, controller: MagicMock) -> None:
    monkeypatch.setattr(mod, "st", _StudioStreamlit)
    monkeypatch.setattr(
        mod,
        "_cached_corrections_studio_transcripts",
        lambda: [
            SimpleNamespace(
                base_name="demo",
                segment_count=3,
                path="/tmp/demo.json",
            )
        ],
    )
    monkeypatch.setattr(mod, "CorrectionsStudioController", lambda: controller)
    monkeypatch.setattr(
        mod, "_corrections_studio_workspace_fragment", lambda *_a, **_k: None
    )


@pytest.mark.unit
def test_start_session_does_not_auto_generate(monkeypatch) -> None:
    import transcriptx.web.page_modules.corrections_studio as mod

    _StudioStreamlit.session_state = {}
    _StudioStreamlit.button_returns = {"Start / Resume Session": True}
    _StudioStreamlit.errors = []
    _StudioStreamlit.rerun_calls = 0
    _StudioStreamlit.select_index = 1

    controller = MagicMock()
    controller.start_or_resume.return_value = SimpleNamespace(
        session_id="sess-1",
        candidates_stale=False,
    )
    controller.generate_candidates = MagicMock()
    _patch_studio(monkeypatch, mod, controller)

    with pytest.raises(_RerunCalled):
        mod.render_corrections_studio()

    ss = _StudioStreamlit.session_state
    assert ss["corrections_studio_session_id"] == "sess-1"
    assert ss.get("corrections_studio_pending_generate") is not True
    assert ss["corrections_studio_active_candidate"] is None
    controller.generate_candidates.assert_not_called()
    assert _StudioStreamlit.rerun_calls == 1


@pytest.mark.unit
def test_generate_candidates_defers_with_force_false(monkeypatch) -> None:
    import transcriptx.web.page_modules.corrections_studio as mod

    _StudioStreamlit.session_state = {
        "corrections_studio_session_id": "sess-1",
    }
    _StudioStreamlit.button_returns = {"Generate Candidates": True}
    _StudioStreamlit.errors = []
    _StudioStreamlit.rerun_calls = 0
    _StudioStreamlit.select_index = 1

    controller = MagicMock()
    controller.generate_candidates = MagicMock()
    _patch_studio(monkeypatch, mod, controller)

    with pytest.raises(_RerunCalled):
        mod.render_corrections_studio()

    ss = _StudioStreamlit.session_state
    assert ss["corrections_studio_pending_generate"] is True
    assert ss["corrections_studio_generate_force"] is False
    controller.generate_candidates.assert_not_called()


@pytest.mark.unit
def test_regenerate_defers_generate_with_force_true(monkeypatch) -> None:
    import transcriptx.web.page_modules.corrections_studio as mod

    _StudioStreamlit.session_state = {
        "corrections_studio_session_id": "sess-1",
        "corrections_studio_active_candidate": "old",
    }
    _StudioStreamlit.button_returns = {"Regenerate Candidates": True}
    _StudioStreamlit.errors = []
    _StudioStreamlit.rerun_calls = 0
    _StudioStreamlit.select_index = 1

    controller = MagicMock()
    controller.generate_candidates = MagicMock()
    _patch_studio(monkeypatch, mod, controller)

    with pytest.raises(_RerunCalled):
        mod.render_corrections_studio()

    ss = _StudioStreamlit.session_state
    assert ss["corrections_studio_pending_generate"] is True
    assert ss["corrections_studio_generate_force"] is True
    assert ss["corrections_studio_active_candidate"] is None
    controller.generate_candidates.assert_not_called()


@pytest.mark.unit
def test_pending_generate_calls_controller_with_force_and_clears_flags(
    monkeypatch,
) -> None:
    import transcriptx.web.page_modules.corrections_studio as mod

    _StudioStreamlit.session_state = {
        "corrections_studio_session_id": "sess-9",
        "corrections_studio_pending_generate": True,
        "corrections_studio_generate_force": True,
        "corrections_studio_preview_cache": {"x": 1},
        "corrections_studio_candidates_stale": True,
    }
    _StudioStreamlit.button_returns = {}
    _StudioStreamlit.errors = []
    _StudioStreamlit.rerun_calls = 0
    _StudioStreamlit.select_index = 1

    controller = MagicMock()
    controller.generate_candidates.return_value = SimpleNamespace(
        commit_aborted=False,
        abort_reason="",
    )
    _patch_studio(monkeypatch, mod, controller)

    with pytest.raises(_RerunCalled):
        mod.render_corrections_studio()

    controller.generate_candidates.assert_called_once_with("sess-9", force=True)
    ss = _StudioStreamlit.session_state
    assert "corrections_studio_pending_generate" not in ss
    assert "corrections_studio_generate_force" not in ss
    assert ss["corrections_studio_candidates_stale"] is False
    assert "corrections_studio_preview_cache" not in ss
    assert "corrections_studio_generation_aborted" not in ss


@pytest.mark.unit
def test_pending_generate_records_abort_reason(monkeypatch) -> None:
    import transcriptx.web.page_modules.corrections_studio as mod

    _StudioStreamlit.session_state = {
        "corrections_studio_session_id": "sess-9",
        "corrections_studio_pending_generate": True,
        "corrections_studio_generate_force": False,
    }
    _StudioStreamlit.button_returns = {}
    _StudioStreamlit.rerun_calls = 0
    _StudioStreamlit.select_index = 1

    controller = MagicMock()
    controller.generate_candidates.return_value = SimpleNamespace(
        commit_aborted=True,
        abort_reason="session_changed",
    )
    _patch_studio(monkeypatch, mod, controller)

    with pytest.raises(_RerunCalled):
        mod.render_corrections_studio()

    controller.generate_candidates.assert_called_once_with("sess-9", force=False)
    assert (
        _StudioStreamlit.session_state["corrections_studio_generation_aborted"]
        == "session_changed"
    )


@pytest.mark.unit
def test_pending_generate_error_surfaces_and_stops(monkeypatch) -> None:
    import transcriptx.web.page_modules.corrections_studio as mod

    _StudioStreamlit.session_state = {
        "corrections_studio_session_id": "sess-9",
        "corrections_studio_pending_generate": True,
        "corrections_studio_generate_force": False,
    }
    _StudioStreamlit.button_returns = {}
    _StudioStreamlit.errors = []
    _StudioStreamlit.rerun_calls = 0
    _StudioStreamlit.select_index = 1

    controller = MagicMock()
    controller.generate_candidates.side_effect = RuntimeError("boom")
    _patch_studio(monkeypatch, mod, controller)

    mod.render_corrections_studio()

    assert any("boom" in e for e in _StudioStreamlit.errors)
    assert _StudioStreamlit.rerun_calls == 0
