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
    command_from_workspace_result,
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
    assert (
        speaker_id_workspace_component_enabled(
            {"speaker_id_workspace_component": False}
        )
        is False
    )


def test_flag_session_override_on(monkeypatch) -> None:
    monkeypatch.delenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", raising=False)
    # Explicit True still works when someone clears default via other means.
    assert (
        speaker_id_workspace_component_enabled({"speaker_id_workspace_component": True})
        is True
    )


def test_flag_env_wins_over_session(monkeypatch) -> None:
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "0")
    assert (
        speaker_id_workspace_component_enabled({"speaker_id_workspace_component": True})
        is False
    )
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "1")
    assert (
        speaker_id_workspace_component_enabled(
            {"speaker_id_workspace_component": False}
        )
        is True
    )


def test_flag_blank_env_falls_through_to_session_then_default(monkeypatch) -> None:
    monkeypatch.setenv("TX_SPEAKER_ID_WORKSPACE_COMPONENT", "   ")
    assert (
        speaker_id_workspace_component_enabled(
            {"speaker_id_workspace_component": False}
        )
        is False
    )
    assert speaker_id_workspace_component_enabled({}) is True


def test_clip_transport_roundtrip() -> None:
    raw = b"ID3fake"
    enc = encode_clip_b64(raw)
    assert decode_clip_b64(enc) == raw
    assert within_clip_budget(len(raw), 100)
    assert not within_clip_budget(200, 100)
    assert not within_clip_budget(-1, 100)


def test_stable_workspace_key_is_transcript_scoped() -> None:
    a = stable_workspace_key("/data/a.json")
    b = stable_workspace_key("/data/b.json")
    assert a.startswith("speaker_id_ws:")
    assert a != b


def test_command_from_workspace_result_accepts_dict_and_attr() -> None:
    assert command_from_workspace_result(None) is None
    assert command_from_workspace_result({"command": None}) is None
    assert command_from_workspace_result({"command": {}}) is None
    assert command_from_workspace_result({"command": {"action": "   "}}) is None
    envelope = {
        "action": "navigate_jump",
        "payload": {"target_speaker_id": "SPEAKER_01"},
    }
    assert command_from_workspace_result({"command": envelope}) == envelope
    assert (
        command_from_workspace_result(SimpleNamespace(command=envelope)) == envelope
    )


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
    assert data["paging"]["shown"] == 1
    assert data["paging"]["total"] == 1
    assert ctrl.joined == 0


def test_build_workspace_data_shows_all_samples_but_caps_warm(
    tmp_path: Path,
) -> None:
    """Display is not truncated to MAX_CLIPS_PER_WARM; only warm enqueue is."""
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    enqueued: list[tuple[float, float]] = []

    class _Ctrl:
        def cached_clip_status(self, *_a, start=None, end=None, **_k):
            # Positional after transcript: start, end
            return SimpleNamespace(status="miss", clip_id="c", path=None, reason=None)

        def get_cached_clip_bytes(self, *_a, **_k):
            return None

        def enqueue_clip(self, _tx, start, end, **_k):
            enqueued.append((start, end))
            return SimpleNamespace(status="accepted", clip_id="c")

        def ffmpeg_available(self) -> bool:
            return True

    samples = [{"start": float(i), "end": float(i) + 0.5, "text": f"t{i}"} for i in range(12)]
    data = build_workspace_data(
        transcript_path=str(transcript),
        speaker_ids=["SPEAKER_00"],
        active_speaker_id="SPEAKER_00",
        speaker_labels={"SPEAKER_00": "1. SPEAKER_00"},
        speaker_map={},
        ignored_speakers=[],
        samples=samples,
        controller=_Ctrl(),
        samples_total=20,
        samples_page_size=10,
    )
    assert len(data["samples"]) == 12
    assert len(enqueued) == 8  # MAX_CLIPS_PER_WARM
    assert data["paging"] == {"shown": 12, "total": 20, "page_size": 10}


def test_dispatch_enqueue_clip_calls_controller(tmp_path: Path) -> None:
    from transcriptx.web.workspaces.speaker_id_bridge import dispatch_workspace_command

    calls: list[tuple] = []

    class _Ctrl:
        def enqueue_clip(self, path, start, end, **_k):
            calls.append((path, start, end))
            return SimpleNamespace(status="accepted")

    out = dispatch_workspace_command(
        {
            "action": "enqueue_clip",
            "action_id": "e1",
            "action_seq": 1,
            "payload": {"start": 1.5, "end": 2.5},
        },
        service=SimpleNamespace(),  # type: ignore[arg-type]
        speaker_ids=["SPEAKER_00"],
        current_speaker_idx=0,
        apply_ack=lambda *_a, **_k: None,
        controller=_Ctrl(),
        transcript_path=str(tmp_path / "t.json"),
    )
    assert out is not None and out["status"] == "ok"
    assert calls == [(str(tmp_path / "t.json"), 1.5, 2.5)]


def test_dispatch_load_more_samples_invokes_callback() -> None:
    from transcriptx.web.workspaces.speaker_id_bridge import dispatch_workspace_command

    seen: list[int | None] = []
    out = dispatch_workspace_command(
        {
            "action": "load_more_samples",
            "action_id": "m1",
            "action_seq": 2,
            "payload": {"n": 10},
        },
        service=SimpleNamespace(),  # type: ignore[arg-type]
        speaker_ids=["SPEAKER_00"],
        current_speaker_idx=0,
        apply_ack=lambda *_a, **_k: None,
        on_load_more=seen.append,
    )
    assert out is not None and out["status"] == "ok"
    assert seen == [10]


def test_build_workspace_data_hit_encodes_clip_within_budget(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    blob = b"ID3" + b"x" * 64

    class _Ctrl:
        def cached_clip_status(self, *_a, **_k):
            return SimpleNamespace(
                status="hit", clip_id="c-hit", path=None, reason=None
            )

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


def test_speaker_id_workspace_registers_default_state_callbacks(monkeypatch) -> None:
    """CCv2 rejects ``default`` keys that lack ``on_{name}_change`` callbacks."""
    import sys

    ws_root = Path(__file__).resolve().parents[2] / "packages" / "transcriptx_workspaces"
    monkeypatch.syspath_prepend(str(ws_root))
    sys.modules.pop("transcriptx_workspaces", None)
    import transcriptx_workspaces as ws

    captured: dict = {}

    def _fake_comp(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(command=None, ack_seq=0)

    monkeypatch.setattr(ws, "_get_speaker_id_component", lambda: _fake_comp)
    ws.speaker_id_workspace(data={"protocol_version": "1"}, key="speaker_id_ws:test")

    default_keys = set(captured["default"])
    callback_names = {
        name[3:-7]
        for name in captured
        if name.startswith("on_") and name.endswith("_change")
    }
    # State defaults must be a subset of registered on_*_change callbacks.
    assert default_keys <= callback_names
    # ack_seq is state; command is trigger-only (must not appear in default).
    assert default_keys == {"ack_seq"}
    assert "command" not in default_keys
    assert "command" in callback_names
    assert callable(captured["on_ack_seq_change"])
    assert callable(captured["on_command_change"])


def test_build_workspace_data_inflight_is_pending_without_reenqueue(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    enqueued: list[tuple] = []

    class _Ctrl:
        def cached_clip_status(self, *_a, **_k):
            return SimpleNamespace(status="inflight", clip_id="c-in", path=None, reason=None)

        def get_cached_clip_bytes(self, *_a, **_k):
            return None

        def enqueue_clip(self, *a, **k):
            enqueued.append((a, k))
            return SimpleNamespace(status="already_inflight")

        def ffmpeg_available(self) -> bool:
            return True

    data = build_workspace_data(
        transcript_path=str(transcript),
        speaker_ids=["SPEAKER_00"],
        active_speaker_id="SPEAKER_00",
        speaker_labels={"SPEAKER_00": "1. SPEAKER_00"},
        speaker_map={},
        ignored_speakers=[],
        samples=[{"start": 0.0, "end": 1.0, "text": "hi"}],
        controller=_Ctrl(),
    )
    assert data["samples"][0]["clip_status"] == "pending"
    assert data["samples"][0]["clip_b64"] is None
    assert enqueued == []


def test_build_workspace_data_second_pass_hit_includes_b64(tmp_path: Path) -> None:
    """Miss then hit: the second data build must carry clip_b64 for autoplay."""
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    blob = b"ID3" + b"y" * 32
    hits = {"n": 0}

    class _Ctrl:
        def cached_clip_status(self, *_a, **_k):
            if hits["n"]:
                return SimpleNamespace(status="hit", clip_id="c1", path=None, reason=None)
            return SimpleNamespace(status="miss", clip_id="c1", path=None, reason=None)

        def get_cached_clip_bytes(self, *_a, **_k):
            return blob if hits["n"] else None

        def enqueue_clip(self, *_a, **_k):
            return SimpleNamespace(status="accepted")

        def ffmpeg_available(self) -> bool:
            return True

    kwargs = dict(
        transcript_path=str(transcript),
        speaker_ids=["SPEAKER_00"],
        active_speaker_id="SPEAKER_00",
        speaker_labels={"SPEAKER_00": "1. SPEAKER_00"},
        speaker_map={},
        ignored_speakers=[],
        samples=[{"start": 0.0, "end": 1.0, "text": "hi"}],
        controller=_Ctrl(),
    )
    first = build_workspace_data(**kwargs)
    assert first["samples"][0]["clip_status"] == "pending"
    assert first["samples"][0]["clip_b64"] is None
    hits["n"] = 1
    second = build_workspace_data(**kwargs)
    assert second["samples"][0]["clip_status"] == "hit"
    assert second["samples"][0]["clip_b64"] == encode_clip_b64(blob)


def test_dispatch_refresh_clips_is_ok_noop() -> None:
    from transcriptx.web.workspaces.speaker_id_bridge import dispatch_workspace_command

    out = dispatch_workspace_command(
        {
            "action": "refresh_clips",
            "action_id": "r1",
            "action_seq": 9,
        },
        service=SimpleNamespace(),  # type: ignore[arg-type]
        speaker_ids=["SPEAKER_00"],
        current_speaker_idx=0,
        apply_ack=lambda *_a, **_k: None,
    )
    assert out is not None and out["status"] == "ok"
    assert out["action_id"] == "r1"


def test_build_workspace_data_clip_too_large_skips_b64(tmp_path: Path) -> None:
    from transcriptx.web.workspaces.speaker_id_bridge import MAX_BYTES_PER_CLIP

    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")
    oversized = b"x" * (MAX_BYTES_PER_CLIP + 1)

    class _Ctrl:
        def cached_clip_status(self, *_a, **_k):
            return SimpleNamespace(status="hit", clip_id="c-big", path=None, reason=None)

        def get_cached_clip_bytes(self, *_a, **_k):
            return oversized

        def enqueue_clip(self, *_a, **_k):
            raise AssertionError("too_large must not enqueue")

        def ffmpeg_available(self) -> bool:
            return True

    data = build_workspace_data(
        transcript_path=str(transcript),
        speaker_ids=["SPEAKER_00"],
        active_speaker_id="SPEAKER_00",
        speaker_labels={"SPEAKER_00": "1. SPEAKER_00"},
        speaker_map={},
        ignored_speakers=[],
        samples=[{"start": 0.0, "end": 1.0, "text": "hi"}],
        controller=_Ctrl(),
    )
    sample = data["samples"][0]
    assert sample["clip_status"] == "too_large"
    assert sample["clip_b64"] is None


def test_build_workspace_data_hit_without_bytes_keeps_status(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")

    class _Ctrl:
        def cached_clip_status(self, *_a, **_k):
            return SimpleNamespace(status="hit", clip_id="c-empty", path=None, reason=None)

        def get_cached_clip_bytes(self, *_a, **_k):
            return None

        def enqueue_clip(self, *_a, **_k):
            raise AssertionError("hit must not enqueue")

        def ffmpeg_available(self) -> bool:
            return True

    data = build_workspace_data(
        transcript_path=str(transcript),
        speaker_ids=["SPEAKER_00"],
        active_speaker_id="SPEAKER_00",
        speaker_labels={"SPEAKER_00": "1. SPEAKER_00"},
        speaker_map={},
        ignored_speakers=[],
        samples=[{"start": 0.0, "end": 1.0, "text": "hi"}],
        controller=_Ctrl(),
    )
    sample = data["samples"][0]
    assert sample["clip_status"] == "hit"
    assert sample["clip_b64"] is None


def test_build_workspace_data_marks_ignored_speakers(tmp_path: Path) -> None:
    transcript = tmp_path / "t.json"
    transcript.write_text("{}", encoding="utf-8")

    class _Ctrl:
        def cached_clip_status(self, *_a, **_k):
            return SimpleNamespace(status="miss", clip_id="c1", path=None, reason=None)

        def get_cached_clip_bytes(self, *_a, **_k):
            return None

        def enqueue_clip(self, *_a, **_k):
            return SimpleNamespace(status="accepted")

        def ffmpeg_available(self) -> bool:
            return True

    data = build_workspace_data(
        transcript_path=str(transcript),
        speaker_ids=["SPEAKER_00", "SPEAKER_01"],
        active_speaker_id="SPEAKER_00",
        speaker_labels={
            "SPEAKER_00": "1. SPEAKER_00",
            "SPEAKER_01": "2. SPEAKER_01",
        },
        speaker_map={},
        ignored_speakers=["SPEAKER_01"],
        samples=[{"start": 0.0, "end": 1.0, "text": "hi"}],
        controller=_Ctrl(),
    )
    by_id = {row["id"]: row for row in data["speakers"]}
    assert by_id["SPEAKER_00"]["ignored"] is False
    assert by_id["SPEAKER_01"]["ignored"] is True


def test_dispatch_navigate_jump_unknown_speaker_falls_back() -> None:
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
                active_speaker_id="SPEAKER_00",
                active_speaker_idx=0,
                effects=SpeakerIdEffects(),
            )

    out = dispatch_workspace_command(
        {
            "action": "navigate_jump",
            "action_id": "nav2",
            "action_seq": 3,
            "protocol_version": "1",
            "frontend_build_id": "legacy",
            "transcript_id": "/t.json",
            "payload": {"target_speaker_id": "SPEAKER_99"},
        },
        service=_Svc(),  # type: ignore[arg-type]
        speaker_ids=["SPEAKER_00", "SPEAKER_01"],
        current_speaker_idx=0,
        apply_ack=lambda _a: None,
    )
    assert out is not None and out["status"] == "ok"
    assert seen["payload"]["target_idx"] == 0

