"""Contracts for voice operator settings (bootstrap link cap)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1
from transcriptx.core.speaker_profiles.operations import relative_profile_path
from transcriptx.core.speaker_profiles.store_io import dumps_model, utc_now_iso
from transcriptx.core.speaker_profiles.voice.bootstrap import VoiceBootstrapService
from transcriptx.core.speaker_profiles.voice.models import VoiceOperatorSettingsV1
from transcriptx.core.speaker_profiles.voice.operator import (
    VoiceOperatorStore,
    default_operator_settings,
)
from transcriptx.core.speaker_profiles.voice.operator_service import (
    VoiceOperatorService,
)
from transcriptx.core.speaker_profiles.voice.privacy import VoicePrivacyStore
from transcriptx.core.speaker_profiles.voice.versioning import (
    BOOTSTRAP_MAX_LINKS_MAX,
    DEFAULT_BOOTSTRAP_MAX_LINKS,
    OPERATOR_SETTINGS_SCHEMA_ID,
)


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


@pytest.mark.unit
def test_default_operator_settings_raise_link_cap() -> None:
    settings = default_operator_settings()
    assert settings.schema_id == OPERATOR_SETTINGS_SCHEMA_ID
    assert settings.bootstrap_max_links == DEFAULT_BOOTSTRAP_MAX_LINKS
    assert DEFAULT_BOOTSTRAP_MAX_LINKS == 40


@pytest.mark.unit
def test_operator_settings_reject_out_of_range() -> None:
    with pytest.raises((SpeakerProfileContractError, ValidationError)):
        VoiceOperatorSettingsV1(bootstrap_max_links=0)
    with pytest.raises((SpeakerProfileContractError, ValidationError)):
        VoiceOperatorSettingsV1(bootstrap_max_links=BOOTSTRAP_MAX_LINKS_MAX + 1)


@pytest.mark.contract
def test_operator_service_persists_bootstrap_max_links(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    svc = VoiceOperatorService(root=root, state_dir=state)
    updated = svc.update_bootstrap_max_links(
        operation_idempotency_key="op-cap-1",
        bootstrap_max_links=55,
        actor="tester",
    )
    assert updated.bootstrap_max_links == 55
    assert VoiceOperatorStore(root).read().bootstrap_max_links == 55
    replay = svc.update_bootstrap_max_links(
        operation_idempotency_key="op-cap-1",
        bootstrap_max_links=99,
        actor="tester",
    )
    assert replay.bootstrap_max_links == 55


@pytest.mark.contract
def test_bootstrap_reads_operator_max_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "speaker_profiles"
    _write_active_profile(root)
    VoicePrivacyStore(root).enable(actor="test")
    VoiceOperatorStore(root).write_atomic(
        VoiceOperatorSettingsV1(bootstrap_max_links=2)
    )

    links = root / "links"
    links.mkdir()
    for i in range(5):
        (links / f"link{i:02d}.speaker_link.json").write_text("{}", encoding="utf-8")

    confirmed = []
    for i in range(5):
        confirmed.append(
            type(
                "L",
                (),
                {
                    "profile_id": "p1",
                    "status": "confirmed",
                    "managed_transcript_id": f"t{i}",
                    "local_speaker_key": "SPEAKER_00",
                },
            )()
        )

    def _read(key: str, root=None):  # noqa: ANN001
        idx = int(key.replace("link", ""))
        return confirmed[idx]

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.voice.bootstrap.read_live_link",
        _read,
    )

    calls: list[str] = []

    def _enrol(self, **kwargs):  # noqa: ANN001
        calls.append(kwargs["link_file_key_value"])
        from transcriptx.core.speaker_profiles.voice.bootstrap import (
            BootstrapLinkResult,
        )

        return BootstrapLinkResult(
            link_file_key=kwargs["link_file_key_value"],
            sample_ids=("s",),
            outcome="Enrolled",
        )

    monkeypatch.setattr(
        "transcriptx.core.speaker_profiles.voice.bootstrap.VoiceBootstrapService._enrol_one_link",
        _enrol,
    )

    svc = VoiceBootstrapService(root=root, state_dir=tmp_path / "state")
    svc.generations = type(
        "G",
        (),
        {
            "ensure_default_generation_and_activate": lambda self, **_k: type(
                "P", (), {"model_generation_id": "gen"}
            )()
        },
    )()

    result = svc.enrol_profile_confirmed_links(
        operation_idempotency_key="op-cap",
        profile_id="p1",
        require_activation=False,
    )
    assert result.links_attempted == 2
    assert len(calls) == 2
