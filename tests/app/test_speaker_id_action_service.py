"""Unit tests for SpeakerIdActionService (Theme C Phase −1)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from transcriptx.app.speaker_id import (
    PROTOCOL_VERSION,
    SpeakerIdActionService,
    SpeakerIdCommand,
    mapping_revision_from_state,
    new_action_id,
    transcript_revision_from_path,
)
from transcriptx.io.speaker_map_resolver import SpeakerMapState


class _FakeIndex:
    def __init__(self, ids: tuple[str, ...]):
        self.ordered_speaker_ids = ids


class _FakeController:
    def __init__(self) -> None:
        self.speaker_map: dict[str, str] = {}
        self.ignored_speakers: list[str] = []
        self.mutations: list[tuple] = []

    def get_mapping_status(self, _path: str) -> SpeakerMapState:
        return SpeakerMapState(
            has_sidecar=True,
            speaker_map=dict(self.speaker_map),
            ignored_speakers=list(self.ignored_speakers),
        )

    def apply_mapping_mutation(self, path, did, name, method="web"):
        self.mutations.append(("assign", path, did, name, method))
        self.speaker_map[did] = name
        return self.get_mapping_status(path)

    def ignore_speaker(self, path, did, method="web"):
        self.mutations.append(("ignore", path, did, method))
        if did not in self.ignored_speakers:
            self.ignored_speakers.append(did)
        return self.get_mapping_status(path)

    def unignore_speaker(self, path, did, method="web"):
        self.mutations.append(("unignore", path, did, method))
        self.ignored_speakers = [s for s in self.ignored_speakers if s != did]
        return self.get_mapping_status(path)


@pytest.fixture
def transcript(tmp_path: Path) -> Path:
    p = tmp_path / "meeting.json"
    p.write_text(
        '{"segments":[{"start":0,"end":1,"text":"hi","speaker":"SPEAKER_00"},'
        '{"start":1,"end":2,"text":"yo","speaker":"SPEAKER_01"}]}',
        encoding="utf-8",
    )
    return p


def _service(ctrl: _FakeController, ids=("SPEAKER_00", "SPEAKER_01")):
    return SpeakerIdActionService(
        ctrl,  # type: ignore[arg-type]
        index_loader=lambda _p: _FakeIndex(ids),
        profile_context_resolver=lambda _p: SimpleNamespace(is_managed=False),
    )


def test_save_name_advances_and_is_idempotent(transcript: Path) -> None:
    ctrl = _FakeController()
    svc = _service(ctrl)
    action_id = new_action_id()
    cmd = SpeakerIdCommand(
        action="save_name",
        transcript_id=str(transcript),
        action_id=action_id,
        action_seq=1,
        current_speaker_idx=0,
        expected_speaker_id="SPEAKER_00",
        transcript_revision=transcript_revision_from_path(transcript),
        expected_mapping_revision=mapping_revision_from_state({}, []),
        payload={"display_name": "Alice", "link_profile": False},
    )
    ack1 = svc.execute(cmd)
    assert ack1.status == "ok"
    assert ack1.active_speaker_idx == 1
    assert ack1.effects.navigate_to_idx == 1
    assert ack1.effects.sync_jump is True
    assert ctrl.speaker_map["SPEAKER_00"] == "Alice"
    ack2 = svc.execute(cmd)
    assert ack2 is ack1
    assert len(ctrl.mutations) == 1


def test_stale_expected_speaker_rejects_without_mutation(transcript: Path) -> None:
    ctrl = _FakeController()
    svc = _service(ctrl)
    ack = svc.execute(
        SpeakerIdCommand(
            action="save_name",
            transcript_id=str(transcript),
            action_id=new_action_id(),
            action_seq=1,
            current_speaker_idx=0,
            expected_speaker_id="SPEAKER_01",
            payload={"display_name": "Alice"},
        )
    )
    assert ack.status == "rejected_stale"
    assert ctrl.mutations == []
    assert ack.effects.flashes[0].level == "warning"


def test_protocol_mismatch_fails_closed(transcript: Path) -> None:
    ctrl = _FakeController()
    svc = _service(ctrl)
    ack = svc.execute(
        SpeakerIdCommand(
            action="save_name",
            transcript_id=str(transcript),
            action_id=new_action_id(),
            action_seq=1,
            current_speaker_idx=0,
            expected_speaker_id="SPEAKER_00",
            protocol_version="999",
            payload={"display_name": "Alice"},
        )
    )
    assert ack.status == "rejected_protocol"
    assert ctrl.mutations == []
    assert PROTOCOL_VERSION == "1"


def test_ignore_toggle_and_completion_flag(transcript: Path) -> None:
    ctrl = _FakeController()
    svc = _service(ctrl, ids=("SPEAKER_00",))
    ack = svc.execute(
        SpeakerIdCommand(
            action="ignore_toggle",
            transcript_id=str(transcript),
            action_id=new_action_id(),
            action_seq=1,
            current_speaker_idx=0,
            expected_speaker_id="SPEAKER_00",
            transcript_revision=transcript_revision_from_path(transcript),
            expected_mapping_revision=mapping_revision_from_state({}, []),
        )
    )
    assert ack.status == "ok"
    assert "SPEAKER_00" in ctrl.ignored_speakers
    assert ack.effects.requires_app_rerun is True


def test_navigate_jump_does_not_sync_jump_key(transcript: Path) -> None:
    ctrl = _FakeController()
    svc = _service(ctrl)
    ack = svc.execute(
        SpeakerIdCommand(
            action="navigate_jump",
            transcript_id=str(transcript),
            action_id=new_action_id(),
            action_seq=3,
            current_speaker_idx=0,
            payload={"target_idx": 1},
        )
    )
    assert ack.status == "ok"
    assert ack.effects.navigate_to_idx == 1
    assert ack.effects.sync_jump is False


def test_navigate_jump_rejects_when_expected_is_target_not_current(
    transcript: Path,
) -> None:
    """Frontend must send the current active id as expected_speaker_id.

    Speaker-list clicks set an optimistic *target* in the UI; if that target
    is also sent as expected_speaker_id, navigate_jump is rejected_stale and
    appears as a no-op.
    """
    ctrl = _FakeController()
    svc = _service(ctrl)
    ack = svc.execute(
        SpeakerIdCommand(
            action="navigate_jump",
            transcript_id=str(transcript),
            action_id=new_action_id(),
            action_seq=4,
            current_speaker_idx=0,
            expected_speaker_id="SPEAKER_01",
            payload={"target_idx": 1},
        )
    )
    assert ack.status == "rejected_stale"
    assert ack.active_speaker_idx == 0


def test_navigate_jump_ok_when_expected_matches_current(transcript: Path) -> None:
    ctrl = _FakeController()
    svc = _service(ctrl)
    ack = svc.execute(
        SpeakerIdCommand(
            action="navigate_jump",
            transcript_id=str(transcript),
            action_id=new_action_id(),
            action_seq=5,
            current_speaker_idx=0,
            expected_speaker_id="SPEAKER_00",
            payload={"target_idx": 1},
        )
    )
    assert ack.status == "ok"
    assert ack.active_speaker_idx == 1
    assert ack.active_speaker_id == "SPEAKER_01"


def _managed_service(ctrl: _FakeController, ids=("SPEAKER_00", "SPEAKER_01")):
    return SpeakerIdActionService(
        ctrl,  # type: ignore[arg-type]
        index_loader=lambda _p: _FakeIndex(ids),
        profile_context_resolver=lambda _p: SimpleNamespace(is_managed=True),
    )


def test_save_name_create_mode_calls_create_profile(transcript: Path, monkeypatch) -> None:
    calls: list[dict] = []

    def _fake_create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            effective_signal=None,
            is_partial=False,
            naming_error="",
            link_already_existed=False,
        )

    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.create_and_name.create_profile_link_and_name",
        _fake_create,
    )
    ctrl = _FakeController()
    svc = _managed_service(ctrl)
    ack = svc.execute(
        SpeakerIdCommand(
            action="save_name",
            transcript_id=str(transcript),
            action_id=new_action_id(),
            action_seq=1,
            current_speaker_idx=0,
            expected_speaker_id="SPEAKER_00",
            transcript_revision=transcript_revision_from_path(transcript),
            expected_mapping_revision=mapping_revision_from_state({}, []),
            payload={"display_name": "Maya", "link_mode": "create"},
        )
    )
    assert ack.status == "ok"
    assert len(calls) == 1
    assert calls[0]["display_name"] == "Maya"
    assert calls[0]["create_profile"] is True


def test_save_name_existing_mode_calls_link_existing(
    transcript: Path, monkeypatch
) -> None:
    calls: list[dict] = []

    def _fake_link(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            effective_signal=None,
            is_partial=False,
            naming_error="",
            link_already_existed=False,
        )

    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.create_and_name.link_existing_profile_and_name",
        _fake_link,
    )
    ctrl = _FakeController()
    svc = _managed_service(ctrl)
    ack = svc.execute(
        SpeakerIdCommand(
            action="save_name",
            transcript_id=str(transcript),
            action_id=new_action_id(),
            action_seq=1,
            current_speaker_idx=0,
            expected_speaker_id="SPEAKER_00",
            transcript_revision=transcript_revision_from_path(transcript),
            expected_mapping_revision=mapping_revision_from_state({}, []),
            payload={
                "display_name": "Maya",
                "link_mode": "existing",
                "profile_id": "p-maya",
            },
        )
    )
    assert ack.status == "ok"
    assert len(calls) == 1
    assert calls[0]["profile_id"] == "p-maya"
    assert calls[0]["display_name"] == "Maya"
    assert ctrl.mutations == []  # naming is inside the patched helper


def test_save_name_none_mode_skips_profile_write(
    transcript: Path, monkeypatch
) -> None:
    def _boom(**_kwargs):
        raise AssertionError("profile write should not run")

    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.create_and_name.create_profile_link_and_name",
        _boom,
    )
    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.create_and_name.link_existing_profile_and_name",
        _boom,
    )
    ctrl = _FakeController()
    svc = _managed_service(ctrl)
    ack = svc.execute(
        SpeakerIdCommand(
            action="save_name",
            transcript_id=str(transcript),
            action_id=new_action_id(),
            action_seq=1,
            current_speaker_idx=0,
            expected_speaker_id="SPEAKER_00",
            transcript_revision=transcript_revision_from_path(transcript),
            expected_mapping_revision=mapping_revision_from_state({}, []),
            payload={"display_name": "Maya", "link_mode": "none"},
        )
    )
    assert ack.status == "ok"
    assert ctrl.speaker_map["SPEAKER_00"] == "Maya"


def test_save_name_unmanaged_create_falls_back_to_name_only(
    transcript: Path, monkeypatch
) -> None:
    def _boom(**_kwargs):
        raise AssertionError("unmanaged transcripts must not write profiles")

    monkeypatch.setattr(
        "transcriptx.services.speaker_profiles.create_and_name.create_profile_link_and_name",
        _boom,
    )
    ctrl = _FakeController()
    svc = _service(ctrl)
    ack = svc.execute(
        SpeakerIdCommand(
            action="save_name",
            transcript_id=str(transcript),
            action_id=new_action_id(),
            action_seq=1,
            current_speaker_idx=0,
            expected_speaker_id="SPEAKER_00",
            transcript_revision=transcript_revision_from_path(transcript),
            expected_mapping_revision=mapping_revision_from_state({}, []),
            payload={"display_name": "Maya", "link_mode": "create", "link_profile": True},
        )
    )
    assert ack.status == "ok"
    assert ctrl.speaker_map["SPEAKER_00"] == "Maya"
