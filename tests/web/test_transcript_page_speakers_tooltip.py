"""Tests for transcript page speakers tooltip."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock

import transcriptx.web.page_modules.transcript as mod
from transcriptx.web.transcript_viewer.metadata import speaker_tooltip


def test_transcript_page_speakers_metric_has_help_tooltip() -> None:
    segments = [
        {"speaker": "SPEAKER_00", "speaker_display": "Alice"},
        {"speaker": "SPEAKER_01", "speaker_display": "Bob"},
        {"speaker": "SPEAKER_02", "speaker_display": "Alice"},
    ]
    help_text = speaker_tooltip(segments)
    assert help_text is not None
    assert "- Alice" in help_text
    assert "- Bob" in help_text


def test_metadata_metrics_uses_resolved_segments_for_speaker_tooltip(
    monkeypatch,
) -> None:
    """Speakers help must use mapped names, not raw SPEAKER_XX from the file."""
    captured: dict = {}

    class _DummySt:
        @staticmethod
        def columns(_n):
            return [MagicMock(), MagicMock(), MagicMock(), MagicMock()]

        @staticmethod
        def metric(label, _value, help=None):
            if label == "Speakers":
                captured["help"] = help

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(
        mod, "format_duration_display_from_config", lambda *_a, **_k: "9m"
    )

    raw = {
        "metadata": {"duration_seconds": 540, "speaker_count": 2, "language": "en"},
        "segments": [
            {"speaker": "SPEAKER_00", "text": "hi"},
            {"speaker": "SPEAKER_01", "text": "hey"},
        ],
    }
    resolved = [
        {"speaker": "Alice", "speaker_display": "Alice", "text": "hi"},
        {"speaker": "Bob", "speaker_display": "Bob", "text": "hey"},
    ]
    mod._render_metadata_metrics(raw, resolved)
    assert captured["help"] is not None
    assert "- Alice" in captured["help"]
    assert "- Bob" in captured["help"]
    assert "SPEAKER_" not in captured["help"]


def test_viewer_resolves_speakers_before_metadata_metrics(monkeypatch) -> None:
    """Ensure page wiring resolves names before building the Speakers tooltip."""
    order: list[str] = []
    state: dict = {}

    class _DummySt:
        session_state = state

        @staticmethod
        @contextmanager
        def spinner(_msg):
            yield

        @staticmethod
        def divider():
            return None

        @staticmethod
        def error(_msg):
            return None

        @staticmethod
        def exception(_exc):
            return None

    monkeypatch.setattr(mod, "st", _DummySt)
    monkeypatch.setattr(mod, "render_page_shell", lambda *a, **k: None)
    monkeypatch.setattr(mod, "render_download_row", lambda *a, **k: None)
    monkeypatch.setattr(
        mod,
        "resolve_viewer_preflight",
        lambda *a, **k: MagicMock(
            status="ok",
            context_result=MagicMock(
                selected_session="slug/run",
                run_root="/tmp",
                run_id="run",
                session_slug="slug",
            ),
            subject=None,
        ),
    )
    monkeypatch.setattr(
        mod,
        "load_transcript_with_path_by_session",
        lambda _s: (
            {
                "metadata": {
                    "duration_seconds": 1,
                    "speaker_count": 1,
                    "language": "en",
                },
                "segments": [{"speaker": "SPEAKER_00", "text": "x"}],
            },
            __import__("pathlib").Path("/tmp/t.json"),
        ),
    )
    monkeypatch.setattr(mod, "resolve_transcript_artifacts", lambda **k: MagicMock())

    def _resolve(data, selected):
        order.append("resolve")
        return [{"speaker": "Alice", "speaker_display": "Alice", "text": "x"}]

    def _metrics(data, segments=None):
        order.append("metrics")
        assert segments is not None
        assert segments[0]["speaker_display"] == "Alice"

    monkeypatch.setattr(mod, "_resolve_and_prepare_segments", _resolve)
    monkeypatch.setattr(mod, "_render_metadata_metrics", _metrics)
    monkeypatch.setattr(
        mod,
        "consume_nav_request",
        lambda _s: MagicMock(
            clear_nav_request=False, highlight_query=None, jump_index=None
        ),
    )
    monkeypatch.setattr(mod, "_transcript_interaction_fragment", lambda *a, **k: None)

    mod.render_transcript_viewer()
    assert order == ["resolve", "metrics"]
