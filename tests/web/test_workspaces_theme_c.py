"""Tests for Theme C workspace adapters."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from transcriptx.web.workspaces.clip_transport import (
    decode_clip_b64,
    encode_clip_b64,
    within_clip_budget,
)
from transcriptx.web.workspaces.flags import speaker_id_workspace_component_enabled
from transcriptx.web.workspaces.speaker_id_bridge import (
    build_workspace_data,
    stable_workspace_key,
)


def test_flag_default_off_until_install_proven(monkeypatch) -> None:
    monkeypatch.delenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", raising=False)
    assert speaker_id_workspace_component_enabled({}) is False


def test_flag_env_off_rollback(monkeypatch) -> None:
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "0")
    assert speaker_id_workspace_component_enabled({}) is False


def test_flag_env_on(monkeypatch) -> None:
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "1")
    assert speaker_id_workspace_component_enabled({}) is True


def test_clip_transport_roundtrip() -> None:
    raw = b"ID3fake"
    enc = encode_clip_b64(raw)
    assert decode_clip_b64(enc) == raw
    assert within_clip_budget(len(raw), 100)
    assert not within_clip_budget(200, 100)


def test_stable_workspace_key_is_transcript_scoped() -> None:
    a = stable_workspace_key("/data/a.json")
    b = stable_workspace_key("/data/b.json")
    assert a.startswith("speaker_id_ws:")
    assert a != b


def test_build_workspace_data_uses_nonblocking_clips(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")

    class _Ctrl:
        def __init__(self) -> None:
            self.joined = 0

        def cached_clip_status(self, *_a, **_k):
            return SimpleNamespace(status="miss", clip_id="c1", path=None, reason=None)

        def get_cached_clip_bytes(self, *_a, **_k):
            return None

        def enqueue_clip(self, *_a, **_k):
            return SimpleNamespace(status="accepted", clip_id="c1")

        def get_clip_bytes(self, *_a, **_k):
            self.joined += 1
            raise AssertionError("cold path forbidden")

        def ffmpeg_available(self) -> bool:
            return True

    ctrl = _Ctrl()
    data = build_workspace_data(
        transcript_path=str(transcript),
        speaker_ids=["SPEAKER_00"],
        active_speaker_id="SPEAKER_00",
        speaker_labels={"SPEAKER_00": "1. SPEAKER_00"},
        speaker_map={},
        ignored_speakers=[],
        samples=[{"start": 0.0, "end": 1.0, "text": "hi"}],
        controller=ctrl,
    )
    assert data["protocol_version"] == "1"
    assert data["samples"][0]["clip_status"] == "pending"
    assert ctrl.joined == 0
