"""Web contracts for Theme B transcript viewer corrections."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from transcriptx.web.action_menus.services import PAGE_CORRECTIONS
from transcriptx.web.state import PAGE_KEY
from transcriptx.web.transcript_viewer.corrections_panel import (
    correction_widget_key,
)


def test_correction_widget_key_uses_identity_and_segment_id():
    k1 = correction_widget_key("abcd1234ffff", "seg-A", "w0")
    k2 = correction_widget_key("abcd1234ffff", "seg-B", "w0")
    k3 = correction_widget_key("ffff9999aaaa", "seg-A", "w0")
    assert "seg-A" in k1
    assert k1 != k2
    assert k1 != k3
    assert k1.startswith("tx_corr|")


def test_action_id_correct_in_viewer_registered():
    from transcriptx.web.action_menus.catalog import ACTIONS_BY_ID
    from transcriptx.web.action_menus.handlers import HANDLERS
    from transcriptx.web.action_menus.ids import ActionId

    assert ActionId.CORRECT_IN_VIEWER in ACTIONS_BY_ID
    assert ActionId.CORRECT_IN_VIEWER in HANDLERS


def test_open_studio_uses_identity_nav_not_widget_key_path(monkeypatch, tmp_path):
    """Open Studio must not seed corrections_studio_transcript with a path string."""
    import transcriptx.web.transcript_viewer.corrections_panel as mod

    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}", encoding="utf-8")
    ss: dict = {
        "corrections_studio_transcript": "stale-path-or-index",
    }
    reruns: list[bool] = []

    class _Expander:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    class _St:
        session_state = ss

        @staticmethod
        def expander(*_a, **_k):
            return _Expander()

        @staticmethod
        def selectbox(*_a, **_k):
            return "0: hello"

        @staticmethod
        def text_input(*_a, **_k):
            return ""

        @staticmethod
        def caption(*_a, **_k):
            return None

        @staticmethod
        def warning(*_a, **_k):
            return None

        @staticmethod
        def columns(_n):
            c1, c2, c3 = MagicMock(), MagicMock(), MagicMock()
            c1.button = MagicMock(return_value=False)
            c2.button = MagicMock(return_value=False)
            c3.button = MagicMock(return_value=True)
            return c1, c2, c3

        @staticmethod
        def rerun():
            reruns.append(True)

    monkeypatch.setattr(mod, "st", _St)
    monkeypatch.setattr(
        "transcriptx.web.action_menus.services.st",
        _St,
    )
    monkeypatch.setattr(
        "transcriptx.web.action_menus.services.make_session_path_resolver",
        lambda: None,
    )
    monkeypatch.setattr(
        "transcriptx.web.action_menus.services.SubjectService.set_transcript_context_from_path",
        staticmethod(lambda *_a, **_k: None),
    )

    ctx = SimpleNamespace(
        transcript_path=str(transcript),
        transcript_identity_hash="abcd1234ffff0000",
        segments=[],
    )
    segment = {"id": "seg-1", "text": "hello world", "words": []}

    mod.render_segment_propose_panel(
        ctx=ctx,
        source_index=0,
        segment=segment,
    )

    assert ss[PAGE_KEY] == PAGE_CORRECTIONS
    assert "corrections_studio_transcript" not in ss
    assert reruns == [True]
