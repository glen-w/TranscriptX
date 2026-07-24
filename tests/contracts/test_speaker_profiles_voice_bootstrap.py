"""Offline contracts for voice bootstrap enrolment early paths."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.operations import relative_profile_path
from transcriptx.core.speaker_profiles.store_io import dumps_model, utc_now_iso
from transcriptx.core.speaker_profiles.voice.bootstrap import VoiceBootstrapService
from transcriptx.core.speaker_profiles.voice.privacy import VoicePrivacyStore
from transcriptx.core.speaker_profiles.voice.runtime import ModelUnavailable


def _write_active_profile(root: Path, profile_id: str = "p1") -> None:
    (root / "profiles").mkdir(parents=True, exist_ok=True)
    now = utc_now_iso()
    profile = SpeakerProfileV1(
        profile_id=profile_id,
        display_name=profile_id,
        aliases=[],
        notes=None,
        accent_color="#112233",
        status="active",
        merged_into_profile_id=None,
        created_at=now,
        updated_at=now,
    )
    (root / relative_profile_path(profile_id)).write_bytes(dumps_model(profile))


@pytest.mark.contract
def test_bootstrap_profile_not_found(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    VoicePrivacyStore(root).enable(actor="test")
    svc = VoiceBootstrapService(root=root, state_dir=tmp_path / "state")
    with pytest.raises(SpeakerProfileContractError, match="not found"):
        svc.enrol_profile_confirmed_links(
            operation_idempotency_key="op1",
            profile_id="missing",
        )


@pytest.mark.contract
def test_bootstrap_rejects_non_active_profile(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    (root / "profiles").mkdir(parents=True)
    now = utc_now_iso()
    profile = SpeakerProfileV1(
        profile_id="p1",
        display_name="p1",
        aliases=[],
        notes=None,
        accent_color="#112233",
        status="archived",
        merged_into_profile_id=None,
        created_at=now,
        updated_at=now,
    )
    (root / relative_profile_path("p1")).write_bytes(dumps_model(profile))
    VoicePrivacyStore(root).enable(actor="test")
    svc = VoiceBootstrapService(root=root, state_dir=tmp_path / "state")
    with pytest.raises(SpeakerProfileContractError, match="status"):
        svc.enrol_profile_confirmed_links(
            operation_idempotency_key="op1",
            profile_id="p1",
        )


@pytest.mark.contract
def test_bootstrap_no_confirmed_links_enrols_zero(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    _write_active_profile(root)
    VoicePrivacyStore(root).enable(actor="test")
    svc = VoiceBootstrapService(root=root, state_dir=tmp_path / "state")
    result = svc.enrol_profile_confirmed_links(
        operation_idempotency_key="op-empty",
        profile_id="p1",
    )
    assert result.links_attempted == 0
    assert result.links_enrolled == 0
    assert result.sample_ids == ()
    assert result.per_link == ()


@pytest.mark.contract
def test_bootstrap_model_unavailable_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "speaker_profiles"
    _write_active_profile(root)
    VoicePrivacyStore(root).enable(actor="test")

    links = root / "links"
    links.mkdir()
    # Minimal confirmed link file read by read_live_link via stub.
    link_key = "abc123"
    (links / f"{link_key}.speaker_link.json").write_text("{}", encoding="utf-8")

    link = SimpleNamespace(
        profile_id="p1",
        status="confirmed",
        managed_transcript_id="t1",
        local_speaker_key="SPEAKER_00",
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.voice.bootstrap.read_live_link",
        lambda key, root=None: link if key == link_key else None,
    )
    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.voice.bootstrap.VoiceBootstrapService._enrol_one_link",
        lambda self, **_kwargs: (_ for _ in ()).throw(ModelUnavailable("no model")),
    )

    svc = VoiceBootstrapService(root=root, state_dir=tmp_path / "state")
    # Bypass generation pin network/model work.
    svc.generations = MagicMock()
    svc.generations.ensure_default_generation_and_activate.return_value = (
        SimpleNamespace(model_generation_id="gen")
    )

    result = svc.enrol_profile_confirmed_links(
        operation_idempotency_key="op-mu",
        profile_id="p1",
        require_activation=False,
    )
    assert result.links_attempted == 1
    assert result.links_enrolled == 0
    assert result.per_link[0].outcome == "ModelUnavailable"
