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


def test_flag_default_on(monkeypatch) -> None:
    """Phase 5: CCv2 Speaker ID workspace is the default surface."""
    monkeypatch.delenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", raising=False)
    assert speaker_id_workspace_component_enabled({}) is True
    assert speaker_id_workspace_component_enabled(None) is True


def test_flag_env_off_rollback(monkeypatch) -> None:
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "0")
    assert speaker_id_workspace_component_enabled({}) is False
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "false")
    assert speaker_id_workspace_component_enabled({}) is False
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "off")
    assert speaker_id_workspace_component_enabled({}) is False


def test_flag_env_on(monkeypatch) -> None:
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "1")
    assert speaker_id_workspace_component_enabled({}) is True
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "true")
    assert speaker_id_workspace_component_enabled({}) is True


def test_flag_session_override_off(monkeypatch) -> None:
    monkeypatch.delenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", raising=False)
    assert speaker_id_workspace_component_enabled(
        {"speaker_id_workspace_component": False}
    ) is False


def test_flag_session_override_on(monkeypatch) -> None:
    monkeypatch.delenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", raising=False)
    # Explicit True still works when someone clears default via other means.
    assert speaker_id_workspace_component_enabled(
        {"speaker_id_workspace_component": True}
    ) is True


def test_flag_env_wins_over_session(monkeypatch) -> None:
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "0")
    assert speaker_id_workspace_component_enabled(
        {"speaker_id_workspace_component": True}
    ) is False
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "1")
    assert speaker_id_workspace_component_enabled(
        {"speaker_id_workspace_component": False}
    ) is True


def test_flag_blank_env_falls_through_to_session_then_default(monkeypatch) -> None:
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "   ")
    assert speaker_id_workspace_component_enabled(
        {"speaker_id_workspace_component": False}
    ) is False
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


def test_build_workspace_data_hit_encodes_clip_within_budget(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    blob = b"ID3" + b"x" * 64

    class _Ctrl:
        def cached_clip_status(self, *_a, **_k):
            return SimpleNamespace(status="hit", clip_id="c-hit", path=None, reason=None)

        def get_cached_clip_bytes(self, *_a, **_k):
            return blob

        def enqueue_clip(self, *_a, **_k):
            raise AssertionError("hit must not enqueue")

        def ffmpeg_available(self) -> bool:
            return True

    data = build_workspace_data(
        transcript_path=str(transcript),
        speaker_ids=["SPEAKER_00"],
        active_speaker_id="SPEAKER_00",
        speaker_labels={"SPEAKER_00": "Alice"},
        speaker_map={"SPEAKER_00": "Alice"},
        ignored_speakers=[],
        samples=[{"start": 0.0, "end": 1.0, "text": "hi"}],
        controller=_Ctrl(),
        draft_name="Alice",
        ui_status="1/1 · named",
        last_ack={"status": "ok", "action_seq": 3},
    )
    sample = data["samples"][0]
    assert sample["clip_status"] == "hit"
    assert sample["clip_b64"] == encode_clip_b64(blob)
    assert data["speakers"][0]["named"] is True
    assert data["draft_name"] == "Alice"
    assert data["ack"]["action_seq"] == 3
    assert data["capabilities"]["ffmpeg"] is True


def test_dispatch_ack_includes_authoritative_fields() -> None:
    """Bridge must surface revision/effect fields for optimistic reconciliation."""
    from transcriptx.app.speaker_id import (
        SpeakerIdAck,
        SpeakerIdEffects,
        SpeakerIdFlash,
    )
    from transcriptx.web.workspaces.speaker_id_bridge import dispatch_workspace_command

    class _Svc:
        _expected_builds = set()

        def execute(self, command):
            return SpeakerIdAck(
                action_id=command.action_id,
                action_seq=command.action_seq,
                status="ok",
                transcript_id=command.transcript_id,
                transcript_revision="tr1",
                mapping_revision="mr1",
                active_speaker_id="SPEAKER_00",
                active_speaker_idx=0,
                effects=SpeakerIdEffects(
                    flashes=(SpeakerIdFlash(level="info", message="saved"),),
                    requires_app_rerun=True,
                ),
            )

    applied = []
    out = dispatch_workspace_command(
        {
            "action": "save_name",
            "action_id": "aid1",
            "action_seq": 7,
            "protocol_version": "1",
            "frontend_build_id": "legacy",
            "expected_speaker_id": "SPEAKER_00",
            "payload": {"name": "Alice"},
        },
        service=_Svc(),  # type: ignore[arg-type]
        speaker_ids=["SPEAKER_00"],
        current_speaker_idx=0,
        apply_ack=applied.append,
    )
    assert out is not None
    assert out["status"] == "ok"
    assert out["transcript_revision"] == "tr1"
    assert out["mapping_revision"] == "mr1"
    assert out["active_speaker_id"] == "SPEAKER_00"
    assert out["requires_app_rerun"] is True
    assert out["flashes"] == [{"level": "info", "message": "saved"}]
    assert len(applied) == 1


def test_dispatch_protocol_mismatch_and_empty_command() -> None:
    from transcriptx.web.workspaces.speaker_id_bridge import dispatch_workspace_command

    class _Svc:
        def execute(self, command):  # pragma: no cover - must not run
            raise AssertionError("should not execute")

    assert (
        dispatch_workspace_command(
            None,
            service=_Svc(),  # type: ignore[arg-type]
            speaker_ids=["SPEAKER_00"],
            current_speaker_idx=0,
            apply_ack=lambda _a: None,
        )
        is None
    )
    ack = dispatch_workspace_command(
        {
            "action": "protocol_mismatch",
            "action_id": "a",
            "action_seq": 1,
        },
        service=_Svc(),  # type: ignore[arg-type]
        speaker_ids=["SPEAKER_00"],
        current_speaker_idx=0,
        apply_ack=lambda _a: None,
    )
    assert ack is not None
    assert ack["status"] == "rejected_protocol"


def test_dispatch_navigate_jump_resolves_speaker_id() -> None:
    from transcriptx.app.speaker_id import SpeakerIdAck, SpeakerIdEffects
    from transcriptx.web.workspaces.speaker_id_bridge import dispatch_workspace_command

    seen = {}

    class _Svc:
        _expected_builds = set()

        def execute(self, command):
            seen["payload"] = dict(command.payload)
            return SpeakerIdAck(
                action_id=command.action_id,
                action_seq=command.action_seq,
                status="ok",
                transcript_id=command.transcript_id,
                transcript_revision="tr",
                mapping_revision="mr",
                active_speaker_id="SPEAKER_01",
                active_speaker_idx=1,
                effects=SpeakerIdEffects(),
            )

    out = dispatch_workspace_command(
        {
            "action": "navigate_jump",
            "action_id": "nav1",
            "action_seq": 2,
            "protocol_version": "1",
            "frontend_build_id": "legacy",
            "transcript_id": "/t.json",
            "payload": {"target_speaker_id": "SPEAKER_01"},
        },
        service=_Svc(),  # type: ignore[arg-type]
        speaker_ids=["SPEAKER_00", "SPEAKER_01"],
        current_speaker_idx=0,
        apply_ack=lambda _a: None,
    )
    assert out["status"] == "ok"
    assert seen["payload"]["target_idx"] == 1
