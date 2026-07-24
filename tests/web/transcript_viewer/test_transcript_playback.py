"""Behavioural tests for Transcript playback availability, state, warm, and player."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from transcriptx.services.speaker_studio.segment_index import SegmentInfo
from transcriptx.web.components.playback_panel import (
    PlaybackUnavailableReason,
    resolve_playback_availability,
    trigger_clip_warm,
)
from transcriptx.web.page_modules import transcript as transcript_mod
from transcriptx.web.transcript_viewer.playback_targets import (
    build_playback_targets,
    filtered_view_signature,
)
from transcriptx.web.transcript_viewer.segments import (
    TranscriptPlaybackBinding,
    play_button_key,
)


class _FakeSession(dict):
    """Minimal session_state stand-in."""


def test_availability_unresolved_transcript() -> None:
    controller = MagicMock()
    result = resolve_playback_availability(None, controller)
    assert result.enabled is False
    assert result.reason == PlaybackUnavailableReason.transcript_unresolved
    controller.get_audio_path.assert_not_called()
    controller.ffmpeg_available.assert_not_called()


def test_availability_missing_audio(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    controller = MagicMock()
    controller.get_audio_path.return_value = None
    result = resolve_playback_availability(transcript, controller)
    assert result.enabled is False
    assert result.reason == PlaybackUnavailableReason.audio_missing
    controller.ffmpeg_available.assert_not_called()


def test_availability_missing_ffmpeg(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    controller = MagicMock()
    controller.get_audio_path.return_value = audio
    controller.ffmpeg_available.return_value = False
    result = resolve_playback_availability(transcript, controller)
    assert result.enabled is False
    assert result.reason == PlaybackUnavailableReason.ffmpeg_missing


def test_availability_audio_path_must_be_regular_file(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    missing_audio = tmp_path / "missing.mp3"
    controller = MagicMock()
    controller.get_audio_path.return_value = missing_audio
    result = resolve_playback_availability(transcript, controller)
    assert result.enabled is False
    assert result.reason == PlaybackUnavailableReason.audio_missing
    controller.ffmpeg_available.assert_not_called()


def test_availability_controller_error(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    controller = MagicMock()
    controller.get_audio_path.side_effect = RuntimeError("boom")
    result = resolve_playback_availability(transcript, controller)
    assert result.enabled is False
    assert result.reason == PlaybackUnavailableReason.controller_error


def test_reset_clears_on_owner_and_view_change() -> None:
    state: dict[str, Any] = {
        transcript_mod._PLAY_KEY: 2,
        f"{transcript_mod._PLAY_KEY}_warm_sig": ("old",),
        transcript_mod._OWNER_KEY: ("slug", "run1", "/a.json", 1, 2),
        transcript_mod._VIEW_SIG_KEY: ("old-sig",),
    }
    owner = ("slug", "run1", "/a.json", 1, 2)
    targets = {1: object()}
    transcript_mod.reset_transcript_playback_state_if_needed(
        state,
        owner=owner,
        view_signature=("new-sig",),
        targets=targets,
    )
    assert state[transcript_mod._PLAY_KEY] is None
    assert state[f"{transcript_mod._PLAY_KEY}_warm_sig"] is None
    assert state[transcript_mod._VIEW_SIG_KEY] == ("new-sig",)


def test_reset_unchanged_signature_keeps_active() -> None:
    owner = ("slug", "run1", "/a.json", 10, 20)
    sig = (owner, "", None, ((0, 0.0, 1.0),))
    state: dict[str, Any] = {
        transcript_mod._PLAY_KEY: 0,
        transcript_mod._OWNER_KEY: owner,
        transcript_mod._VIEW_SIG_KEY: sig,
    }
    targets = {0: object()}
    transcript_mod.reset_transcript_playback_state_if_needed(
        state,
        owner=owner,
        view_signature=sig,
        targets=targets,
    )
    assert state[transcript_mod._PLAY_KEY] == 0


def test_reset_rejects_boolean_active_index() -> None:
    owner = ("slug", "run1", "/a.json", 10, 20)
    sig = (owner, "", None, ((1, 1.0, 2.0),))
    state: dict[str, Any] = {
        transcript_mod._PLAY_KEY: True,
        transcript_mod._OWNER_KEY: owner,
        transcript_mod._VIEW_SIG_KEY: sig,
    }
    transcript_mod.reset_transcript_playback_state_if_needed(
        state,
        owner=owner,
        view_signature=sig,
        targets={1: object()},
    )
    assert state[transcript_mod._PLAY_KEY] is None


def test_reset_clears_stale_active_absent_from_targets() -> None:
    owner = ("slug", "run1", "/a.json", 10, 20)
    sig = (owner, "", None, ((1, 1.0, 2.0),))
    state: dict[str, Any] = {
        transcript_mod._PLAY_KEY: 99,
        transcript_mod._OWNER_KEY: owner,
        transcript_mod._VIEW_SIG_KEY: sig,
    }
    transcript_mod.reset_transcript_playback_state_if_needed(
        state,
        owner=owner,
        view_signature=sig,
        targets={1: object()},
    )
    assert state[transcript_mod._PLAY_KEY] is None


def test_either_tab_callback_writes_same_play_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binding = TranscriptPlaybackBinding(
        enabled=True,
        targets={
            4: SegmentInfo(index=4, start=1.0, end=2.0, text="x", speaker="A"),
        },
        play_key=transcript_mod._PLAY_KEY,
        owner_prefix="slug|run|/t.json",
    )
    # Keys differ by tab but on_click args share play_key + source index.
    assert play_button_key(binding, "turns", 4) != play_button_key(
        binding, "segments", 4
    )
    from transcriptx.web.components import playback_panel as panel

    captured: dict[str, Any] = {}

    def _capture(play_key: str, idx: int) -> None:
        captured["play_key"] = play_key
        captured["idx"] = idx

    monkeypatch.setattr(panel, "set_active_clip", _capture)
    panel.set_active_clip(binding.play_key, 4)
    assert captured == {"play_key": transcript_mod._PLAY_KEY, "idx": 4}
    panel.set_active_clip(binding.play_key, 4)
    assert captured["idx"] == 4


def test_trigger_clip_warm_once_per_signature(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from transcriptx.services.speaker_studio.clip_service import WarmClipsResult

    session: dict[str, Any] = {}
    monkeypatch.setattr(
        "transcriptx.web.components.playback_panel.st.session_state",
        session,
    )
    controller = MagicMock()
    controller.warm_clips.return_value = WarmClipsResult(
        accepted=3,
        enqueued=3,
        already_cached=0,
        already_inflight=0,
        requested=3,
    )
    segs = [
        SegmentInfo(index=0, start=0.0, end=1.0, text="a", speaker="A"),
        SegmentInfo(index=1, start=1.0, end=2.0, text="b", speaker="A"),
        SegmentInfo(index=2, start=2.0, end=3.0, text="c", speaker="A"),
    ]
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    trigger_clip_warm(controller, "/t.json", audio, segs, None, "owner", "play_key")
    trigger_clip_warm(controller, "/t.json", audio, segs, None, "owner", "play_key")
    assert controller.warm_clips.call_count == 1
    # Active at position 1 warms from that segment onward.
    session.clear()
    controller.warm_clips.return_value = WarmClipsResult(
        accepted=2,
        enqueued=2,
        already_cached=0,
        already_inflight=0,
        requested=2,
    )
    trigger_clip_warm(controller, "/t.json", audio, segs, 1, "owner", "play_key")
    args = controller.warm_clips.call_args[0]
    assert args[1] == [(1.0, 2.0), (2.0, 3.0)]


def test_trigger_clip_warm_does_not_set_sig_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    session: dict[str, Any] = {}
    monkeypatch.setattr(
        "transcriptx.web.components.playback_panel.st.session_state",
        session,
    )
    controller = MagicMock()
    controller.warm_clips.side_effect = RuntimeError("enqueue failed")
    segs = [SegmentInfo(index=0, start=0.0, end=1.0, text="a", speaker="A")]
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    trigger_clip_warm(controller, "/t.json", audio, segs, None, "owner", "play_key")
    assert "play_key_warm_sig" not in session
    # Retry allowed.
    controller.warm_clips.side_effect = None
    from transcriptx.services.speaker_studio.clip_service import WarmClipsResult

    controller.warm_clips.return_value = WarmClipsResult(
        accepted=1,
        enqueued=1,
        already_cached=0,
        already_inflight=0,
        requested=1,
    )
    trigger_clip_warm(controller, "/t.json", audio, segs, None, "owner", "play_key")
    assert "play_key_warm_sig" in session
    assert controller.warm_clips.call_count == 2


def test_trigger_clip_warm_retries_after_transient_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from transcriptx.services.speaker_studio.clip_service import WarmClipsResult

    session: dict[str, Any] = {}
    monkeypatch.setattr(
        "transcriptx.web.components.playback_panel.st.session_state",
        session,
    )
    controller = MagicMock()
    controller.warm_clips.return_value = WarmClipsResult(
        accepted=0,
        enqueued=0,
        already_cached=0,
        already_inflight=0,
        requested=1,
        stopped_reason="ffmpeg_missing",
    )
    segs = [SegmentInfo(index=0, start=0.0, end=1.0, text="a", speaker="A")]
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
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


def test_render_active_clip_success_and_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from transcriptx.web.components import playback_panel as panel

    audio_calls: list[Any] = []
    warnings: list[str] = []

    monkeypatch.setattr(
        panel.st,
        "audio",
        lambda *a, **k: audio_calls.append((a, k)),
    )
    monkeypatch.setattr(
        panel.st,
        "warning",
        lambda msg: warnings.append(msg),
    )

    controller = MagicMock()
    controller.get_clip_bytes.return_value = b"mp3"
    seg = SegmentInfo(index=2, start=1.0, end=2.0, text="x", speaker="A")
    panel.render_active_clip(controller, "/t.json", seg, autoplay=True)
    assert audio_calls
    assert audio_calls[0][1]["format"] == "audio/mpeg"
    assert audio_calls[0][1]["autoplay"] is True

    controller.get_clip_bytes.side_effect = FileNotFoundError("/secret/path.wav")
    panel.render_active_clip(controller, "/t.json", seg, autoplay=True)
    assert warnings
    assert "/secret" not in warnings[0]
    assert "FileNotFoundError" not in warnings[0]


def test_render_active_clip_mounts_idle_player_when_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Idle mount keeps st.audio in layout so first ▶ does not scroll to player."""
    from transcriptx.web.components import playback_panel as panel

    audio_calls: list[Any] = []
    monkeypatch.setattr(
        panel.st,
        "audio",
        lambda *a, **k: audio_calls.append((a, k)),
    )

    controller = MagicMock()
    panel.render_active_clip(controller, "/t.json", None)
    controller.get_clip_bytes.assert_not_called()
    assert len(audio_calls) == 1
    assert audio_calls[0][0][0] == panel._IDLE_CLIP_MP3
    assert audio_calls[0][1]["autoplay"] is False
    assert audio_calls[0][1]["format"] == "audio/mpeg"


def test_no_nested_fragment_in_playback_helpers() -> None:
    import inspect

    from transcriptx.web.components import playback_panel as panel

    source = Path(panel.__file__).read_text()
    # Only render_playback_panel may be decorated with @st.fragment.
    decorator_lines = [
        line for line in source.splitlines() if line.strip() == "@st.fragment"
    ]
    assert len(decorator_lines) == 1
    assert inspect.isfunction(panel.render_active_clip)
    assert inspect.isfunction(panel.trigger_clip_warm)
    assert inspect.isfunction(panel.set_active_clip)
    assert getattr(panel.render_active_clip, "__wrapped__", None) is None


def test_shared_controller_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    from transcriptx.web import speaker_studio_runtime as runtime

    created: list[Any] = []

    class _Ctrl:
        def __init__(self) -> None:
            created.append(self)

        def close(self) -> None:
            pass

    # Bypass Streamlit cache_resource for unit test.
    monkeypatch.setattr(runtime, "SpeakerStudioController", _Ctrl)
    monkeypatch.setattr(runtime, "_atexit_registered", False)

    # Clear and replace cache_resource with a simple singleton.
    singleton: dict[str, Any] = {}

    def _factory() -> Any:
        if "c" not in singleton:
            singleton["c"] = _Ctrl()
            runtime._register_atexit_close(singleton["c"])
        return singleton["c"]

    monkeypatch.setattr(runtime, "get_shared_speaker_studio_controller", _factory)
    a = runtime.get_shared_speaker_studio_controller()
    b = runtime.get_shared_speaker_studio_controller()
    assert a is b
    assert len(created) == 1


def test_build_targets_from_filtered_display_preserves_source() -> None:
    display = [
        (8, {"start": 8.0, "end": 9.0, "text": "only"}),
    ]
    targets = build_playback_targets(display)
    assert 8 in targets
    assert 0 not in targets


def test_canonical_path_prefers_loaded_over_artifacts(tmp_path: Path) -> None:
    loaded = tmp_path / "loaded.json"
    artifact = tmp_path / "artifact.json"
    loaded.write_text("{}")
    artifact.write_text("{}")
    assert (
        transcript_mod._resolve_canonical_transcript_path(loaded, artifact)
        == loaded.resolve()
    )
    assert (
        transcript_mod._resolve_canonical_transcript_path(None, artifact)
        == artifact.resolve()
    )


def test_canonical_path_falls_back_when_loaded_missing(tmp_path: Path) -> None:
    missing = tmp_path / "gone.json"
    artifact = tmp_path / "artifact.json"
    artifact.write_text("{}")
    assert (
        transcript_mod._resolve_canonical_transcript_path(missing, artifact)
        == artifact.resolve()
    )


def test_availability_rejects_directory_transcript(tmp_path: Path) -> None:
    controller = MagicMock()
    result = resolve_playback_availability(tmp_path, controller)
    assert result.enabled is False
    assert result.reason == PlaybackUnavailableReason.transcript_unresolved
    controller.get_audio_path.assert_not_called()


def test_availability_enabled_when_path_audio_ffmpeg_ok(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}")
    audio = tmp_path / "a.mp3"
    audio.write_bytes(b"x")
    controller = MagicMock()
    controller.get_audio_path.return_value = audio
    controller.ffmpeg_available.return_value = True
    result = resolve_playback_availability(transcript, controller)
    assert result.enabled is True
    assert result.audio_path == audio
    assert result.reason is None


def test_trigger_clip_warm_noop_on_empty_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session: dict[str, Any] = {}
    monkeypatch.setattr(
        "transcriptx.web.components.playback_panel.st.session_state",
        session,
    )
    controller = MagicMock()
    trigger_clip_warm(
        controller, "/t.json", Path("/a.mp3"), [], None, "owner", "play_key"
    )
    controller.warm_clips.assert_not_called()


def test_render_active_clip_vanished_audio_after_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extraction re-resolves audio; missing file after preflight must not crash UI."""
    from transcriptx.web.components import playback_panel as panel

    warnings: list[str] = []
    monkeypatch.setattr(panel.st, "audio", lambda *a, **k: None)
    monkeypatch.setattr(panel.st, "warning", lambda msg: warnings.append(msg))
    controller = MagicMock()
    controller.get_clip_bytes.side_effect = FileNotFoundError(
        "No audio file found for transcript: /secret/t.json"
    )
    seg = SegmentInfo(index=0, start=0.0, end=1.0, text="x", speaker="A")
    panel.render_active_clip(controller, "/t.json", seg, autoplay=True)
    assert warnings
    assert "/secret" not in warnings[0]
    # Selecting another segment still works after failure.
    controller.get_clip_bytes.side_effect = None
    controller.get_clip_bytes.return_value = b"ok"
    audio_calls: list[Any] = []
    monkeypatch.setattr(panel.st, "audio", lambda *a, **k: audio_calls.append((a, k)))
    other = SegmentInfo(index=1, start=1.0, end=2.0, text="y", speaker="A")
    panel.render_active_clip(controller, "/t.json", other, autoplay=True)
    assert audio_calls


def test_controller_close_shuts_clip_service(tmp_path: Path) -> None:
    from transcriptx.services.speaker_studio.controller import SpeakerStudioController

    controller = SpeakerStudioController(data_dir=tmp_path)
    controller.close()
    controller.close()  # idempotent
    with pytest.raises(RuntimeError):
        controller._clip_service._executor.submit(lambda: None)
    result = controller.warm_clips("/t.json", [(0.0, 1.0)])
    assert result.stopped_reason == "closed"


def test_transcript_page_uses_shared_controller_not_ctor() -> None:
    source = Path(transcript_mod.__file__).read_text()
    assert "get_shared_speaker_studio_controller" in source
    assert "SpeakerStudioController()" not in source


def test_play_button_eligible_gates_invalid_and_disabled() -> None:
    from transcriptx.web.transcript_viewer.segments import play_button_eligible

    target = SegmentInfo(index=3, start=1.0, end=2.0, text="x", speaker="A")
    enabled = TranscriptPlaybackBinding(
        enabled=True,
        targets={3: target},
        play_key="k",
        owner_prefix="o",
    )
    disabled = TranscriptPlaybackBinding(
        enabled=False,
        targets={3: target},
        play_key="k",
        owner_prefix="o",
    )
    assert play_button_eligible(enabled, 3) is True
    assert play_button_eligible(enabled, 9) is False
    assert play_button_eligible(disabled, 3) is False
    assert play_button_eligible(None, 3) is False


def test_empty_search_clears_active_via_reset_path() -> None:
    """Empty filtered view should clear active and leave no playable targets."""
    state: dict[str, Any] = {
        transcript_mod._PLAY_KEY: 2,
        f"{transcript_mod._PLAY_KEY}_warm_sig": ("x",),
        transcript_mod._OWNER_KEY: ("slug", "run", "/t.json", 1, 2),
        transcript_mod._VIEW_SIG_KEY: ("old",),
    }
    owner = ("slug", "run", "/t.json", 1, 2)
    view_sig = filtered_view_signature(
        owner_identity=owner, display_segments=[], search_text="gone"
    )
    transcript_mod.reset_transcript_playback_state_if_needed(
        state,
        owner=owner,
        view_signature=view_sig,
        targets={},
    )
    assert state[transcript_mod._PLAY_KEY] is None
    assert build_playback_targets([]) == {}


def test_owner_prefix_is_bounded_hash() -> None:
    owner = ("slug", "run", "/very/long/path/to/transcript.json", 12, 34)
    prefix = transcript_mod._owner_prefix(owner)
    assert len(prefix) == 16
    assert "|" not in prefix
    assert prefix == transcript_mod._owner_prefix(owner)


def test_canonical_path_resolve_strict_missing_returns_none(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    assert transcript_mod._resolve_canonical_transcript_path(missing, None) is None


def test_revision_change_clears_playback_state(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text("{}")
    rev1 = transcript_mod.transcript_revision_identity(path)
    owner1 = ("slug", "run", *rev1)
    state: dict[str, Any] = {
        transcript_mod._PLAY_KEY: 0,
        transcript_mod._OWNER_KEY: owner1,
        transcript_mod._VIEW_SIG_KEY: ("sig",),
    }
    path.write_text('{"segments":[]}')
    rev2 = transcript_mod.transcript_revision_identity(path)
    owner2 = ("slug", "run", *rev2)
    assert owner1 != owner2
    transcript_mod.reset_transcript_playback_state_if_needed(
        state,
        owner=owner2,
        view_signature=("sig",),
        targets={0: object()},
    )
    assert state[transcript_mod._PLAY_KEY] is None
