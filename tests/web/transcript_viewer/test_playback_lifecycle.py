"""Lifecycle and sanitisation tests for shared playback infrastructure."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.services.speaker_studio.clip_service import ClipService, WarmClipsResult
from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.web.components.playback_panel import (
    sanitize_lines_shown,
    sanitize_play_index,
    trigger_clip_warm,
)


def test_sanitize_play_index_rejects_bool_negative_oob() -> None:
    assert sanitize_play_index(0, 3) == 0
    assert sanitize_play_index(2, 3) == 2
    assert sanitize_play_index(-1, 3) is None
    assert sanitize_play_index(3, 3) is None
    assert sanitize_play_index(True, 3) is None
    assert sanitize_play_index("1", 3) is None
    assert sanitize_play_index(None, 3) is None


def test_sanitize_lines_shown_clamps_and_restores_default() -> None:
    assert sanitize_lines_shown(5, length=10, default=3) == 5
    assert sanitize_lines_shown(99, length=10, default=3) == 10
    assert sanitize_lines_shown(-1, length=10, default=3) == 3
    assert sanitize_lines_shown("nope", length=10, default=3) == 3
    assert sanitize_lines_shown(True, length=10, default=3) == 3
    assert sanitize_lines_shown(None, length=0, default=3) == 0


def test_listing_caches_do_not_construct_clip_service(tmp_path: Path) -> None:
    """Read-only transcript discovery must not spin ClipService executors."""
    from transcriptx.services.speaker_studio.segment_index import SegmentIndexService
    from transcriptx.web.cache_helpers import _list_transcript_summaries_for_paths

    with patch.object(
        ClipService, "__init__", side_effect=AssertionError("ClipService must not init")
    ):
        assert _list_transcript_summaries_for_paths([]) == []
        assert SegmentIndexService(data_dir=tmp_path).list_transcripts() == []


def test_get_shared_returns_controller_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    from transcriptx.web import speaker_studio_runtime as runtime

    created: list[SpeakerStudioController] = []

    class _Ctrl(SpeakerStudioController):
        def __init__(self) -> None:
            # Minimal stand-in without spinning ClipService in unit isolation.
            self._closed = False
            self._clip_service = MagicMock()
            self._clip_service._executor = MagicMock()
            created.append(self)

        def close(self) -> None:
            self._closed = True

    singleton: dict[str, SpeakerStudioController] = {}

    def _factory() -> SpeakerStudioController:
        if "c" not in singleton:
            ctrl = _Ctrl()
            runtime._register_atexit_close(ctrl)
            singleton["c"] = ctrl
        return singleton["c"]

    monkeypatch.setattr(runtime, "get_shared_speaker_studio_controller", _factory)
    a = runtime.get_shared_speaker_studio_controller()
    b = runtime.get_shared_speaker_studio_controller()
    assert isinstance(a, SpeakerStudioController)
    assert a is b
    assert len(created) == 1
    assert a._closed is False


def test_repeated_acquisitions_share_one_clip_executor(tmp_path: Path) -> None:
    """Page-style repeated get_shared calls must not spawn unbounded ClipServices."""
    from transcriptx.web import speaker_studio_runtime as runtime

    runtime._registered_controllers.clear()
    controllers: list[SpeakerStudioController] = []

    def _factory() -> SpeakerStudioController:
        if not controllers:
            ctrl = SpeakerStudioController(data_dir=tmp_path)
            runtime._register_atexit_close(ctrl)
            controllers.append(ctrl)
        return controllers[0]

    # Simulate Streamlit cache_resource: one construction, many acquisitions.
    for _ in range(5):
        c = _factory()
        assert isinstance(c, SpeakerStudioController)
    assert len(controllers) == 1
    assert len(runtime._registered_controllers) == 1
    # One live executor on the shared ClipService.
    assert controllers[0]._clip_service._closed is False
    controllers[0].close()


def test_clear_shared_closes_then_allows_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from transcriptx.web import speaker_studio_runtime as runtime

    closed: list[object] = []

    class _Ctrl:
        def close(self) -> None:
            closed.append(self)

    first = _Ctrl()
    second = _Ctrl()
    runtime._registered_controllers.clear()
    runtime._register_atexit_close(first)  # type: ignore[arg-type]

    calls = {"n": 0}

    def _clear() -> None:
        calls["n"] += 1
        runtime._registered_controllers.clear()

    monkeypatch.setattr(
        runtime.get_shared_speaker_studio_controller, "clear", _clear, raising=False
    )
    # Bind clear onto a stand-in if the real cache_resource isn't clearable in tests.
    if not hasattr(runtime.get_shared_speaker_studio_controller, "clear"):
        runtime.get_shared_speaker_studio_controller.clear = _clear  # type: ignore[attr-defined]

    runtime.clear_shared_speaker_studio_controller()
    assert first in closed
    assert calls["n"] == 1

    runtime._register_atexit_close(second)  # type: ignore[arg-type]
    assert second in runtime._registered_controllers
    assert first not in runtime._registered_controllers


def test_atexit_closes_all_registered() -> None:
    from transcriptx.web import speaker_studio_runtime as runtime

    class _Ctrl:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1

    first = _Ctrl()
    second = _Ctrl()
    runtime._registered_controllers.clear()
    runtime._register_atexit_close(first)  # type: ignore[arg-type]
    runtime._register_atexit_close(second)  # type: ignore[arg-type]
    runtime._close_registered_controllers()
    assert first.closed == 1
    assert second.closed == 1
    assert runtime._registered_controllers == set()


def test_trigger_clip_warm_requires_warm_clips_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session: dict = {}
    monkeypatch.setattr(
        "transcriptx.web.components.playback_panel.st.session_state",
        session,
    )
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    from transcriptx.services.speaker_studio.segment_index import SegmentInfo

    segs = [SegmentInfo(index=0, start=0.0, end=1.0, text="a", speaker="A")]
    controller = MagicMock()
    controller.warm_clips.return_value = None  # unknown return
    trigger_clip_warm(controller, "/t.json", audio, segs, None, "owner", "play_key")
    assert "play_key_warm_sig" not in session

    controller.warm_clips.return_value = WarmClipsResult(
        accepted=1,
        enqueued=1,
        already_cached=0,
        already_inflight=0,
        requested=1,
    )
    trigger_clip_warm(controller, "/t.json", audio, segs, None, "owner", "play_key")
    assert "play_key_warm_sig" in session


def test_audio_replacement_invalidates_warm_sig(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import time

    session: dict = {}
    monkeypatch.setattr(
        "transcriptx.web.components.playback_panel.st.session_state",
        session,
    )
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    from transcriptx.services.speaker_studio.segment_index import SegmentInfo

    segs = [SegmentInfo(index=0, start=0.0, end=1.0, text="a", speaker="A")]
    controller = MagicMock()
    controller.warm_clips.return_value = WarmClipsResult(
        accepted=1,
        enqueued=1,
        already_cached=0,
        already_inflight=0,
        requested=1,
    )
    trigger_clip_warm(controller, "/t.json", audio, segs, None, "owner", "play_key")
    assert controller.warm_clips.call_count == 1
    time.sleep(0.01)
    audio.write_bytes(b"yy")
    trigger_clip_warm(controller, "/t.json", audio, segs, None, "owner", "play_key")
    assert controller.warm_clips.call_count == 2
