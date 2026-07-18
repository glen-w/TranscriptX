"""Corrections Studio accept / reject / skip review contracts (L3)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.web.streamlit_doubles import DummyColumn, DummyExpander


class _ReviewStreamlit:
    session_state: dict = {}
    button_returns: dict[str, bool] = {}
    rerun_calls: int = 0
    errors: list[str] = []

    @classmethod
    def reset(cls) -> None:
        cls.session_state = {}
        cls.button_returns = {}
        cls.rerun_calls = 0
        cls.errors = []

    @staticmethod
    def markdown(*_a, **_k):
        return None

    @staticmethod
    def caption(*_a, **_k):
        return None

    @staticmethod
    def text_input(*_a, **_k):
        return "fixed"

    @staticmethod
    def text_area(*_a, **_k):
        return ""

    @staticmethod
    def checkbox(*_a, **_k):
        return True

    @staticmethod
    def expander(*_a, **_k):
        return DummyExpander()

    @staticmethod
    def divider():
        return None

    @staticmethod
    def columns(_n):
        return tuple(DummyColumn() for _ in range(_n))

    @classmethod
    def button(cls, label, key=None, **_kwargs):
        if key and key in cls.button_returns:
            return cls.button_returns[key]
        return bool(cls.button_returns.get(label, False))

    @classmethod
    def error(cls, msg, **_kwargs):
        cls.errors.append(str(msg))

    @classmethod
    def rerun(cls):
        cls.rerun_calls += 1


def _candidate(*, cid: str = "cand-1") -> SimpleNamespace:
    return SimpleNamespace(
        kind="typo",
        confidence=0.9,
        sources=[],
        wrong_text="teh",
        right_text="the",
        evidence=None,
        id=cid,
        candidate_id=cid,
    )


@pytest.mark.unit
def test_candidate_accept_all_records_decision(monkeypatch) -> None:
    import transcriptx.web.page_modules.corrections_studio as mod

    _ReviewStreamlit.reset()
    controller = MagicMock()
    controller.get_candidate_local_diff.return_value = SimpleNamespace(diffs=[])
    cand = _candidate()
    monkeypatch.setattr(mod, "st", _ReviewStreamlit)
    monkeypatch.setattr(mod, "_get_candidate_id", lambda _c: "cand-1")
    monkeypatch.setattr(mod, "_candidate_status", lambda _c: "pending")
    monkeypatch.setattr(mod, "_candidate_right_text", lambda _c: "the")
    _ReviewStreamlit.button_returns = {"accept_cand-1": True}

    mod._render_candidate_detail(controller, "sess-1", cand)

    controller.record_decision.assert_called_once()
    args, kwargs = controller.record_decision.call_args
    assert args[:3] == ("sess-1", "cand-1", "accept")
    assert _ReviewStreamlit.rerun_calls == 1


@pytest.mark.unit
def test_candidate_reject_records_decision(monkeypatch) -> None:
    import transcriptx.web.page_modules.corrections_studio as mod

    _ReviewStreamlit.reset()
    controller = MagicMock()
    controller.get_candidate_local_diff.return_value = SimpleNamespace(diffs=[])
    monkeypatch.setattr(mod, "st", _ReviewStreamlit)
    monkeypatch.setattr(mod, "_get_candidate_id", lambda _c: "cand-1")
    monkeypatch.setattr(mod, "_candidate_status", lambda _c: "pending")
    monkeypatch.setattr(mod, "_candidate_right_text", lambda _c: "the")
    _ReviewStreamlit.button_returns = {"reject_cand-1": True}

    mod._render_candidate_detail(controller, "sess-1", _candidate())

    controller.record_decision.assert_called_once_with("sess-1", "cand-1", "reject")
    assert _ReviewStreamlit.rerun_calls == 1


@pytest.mark.unit
def test_candidate_skip_records_decision(monkeypatch) -> None:
    import transcriptx.web.page_modules.corrections_studio as mod

    _ReviewStreamlit.reset()
    controller = MagicMock()
    controller.get_candidate_local_diff.return_value = SimpleNamespace(diffs=[])
    monkeypatch.setattr(mod, "st", _ReviewStreamlit)
    monkeypatch.setattr(mod, "_get_candidate_id", lambda _c: "cand-1")
    monkeypatch.setattr(mod, "_candidate_status", lambda _c: "pending")
    monkeypatch.setattr(mod, "_candidate_right_text", lambda _c: "the")
    _ReviewStreamlit.button_returns = {"skip_cand-1": True}

    mod._render_candidate_detail(controller, "sess-1", _candidate())

    controller.record_decision.assert_called_once_with("sess-1", "cand-1", "skip")
    assert _ReviewStreamlit.rerun_calls == 1
