"""Stage 0: speaker_profiles voice phase — privacy, barrier, provenance, paths."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.path_safety import (
    assert_relpath_under_root,
    assert_safe_relpath,
)
from transcriptx.core.speaker_profiles.provenance import (
    LinkProvenanceV1,
    coerce_link_provenance,
)
from transcriptx.core.speaker_profiles.signals import CacheInvalidationSignal
from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
from transcriptx.core.speaker_profiles.voice.errors import (
    VoiceFeatureDisabled,
)
from transcriptx.core.speaker_profiles.voice.privacy import (
    PRIVACY_NOTICE_VERSION,
    VoicePrivacyStore,
    default_privacy_settings,
)
from transcriptx.core.speaker_profiles.voice.versioning import (
    FEATURE_GATE_COMPLETE,
    PRIVACY_SETTINGS_SCHEMA_ID,
)


@pytest.mark.unit
def test_feature_gate_open_after_stage_8() -> None:
    # Stage 8 exit: gate is open in-tree; privacy still defaults disabled.
    assert FEATURE_GATE_COMPLETE is True


@pytest.mark.unit
def test_activation_barrier_allows_when_privacy_enabled(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    store = VoicePrivacyStore(root)
    store.enable(actor="test")
    barrier = ActivationBarrier(root)
    status = barrier.status()
    # Gate open + privacy enabled + current notice → allowed
    assert status.allowed is True
    assert status.feature_gate_complete is True


@pytest.mark.unit
def test_default_privacy_disabled() -> None:
    settings = default_privacy_settings()
    assert settings.enabled is False
    assert settings.schema_id == PRIVACY_SETTINGS_SCHEMA_ID
    assert settings.privacy_notice_version == PRIVACY_NOTICE_VERSION


@pytest.mark.unit
def test_privacy_store_round_trip(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    store = VoicePrivacyStore(root)
    assert store.read().enabled is False
    enabled = store.enable(actor="alice")
    assert enabled.enabled is True
    assert enabled.consent_actor == "alice"
    assert store.read().enabled is True
    revoked = store.revoke(actor="alice")
    assert revoked.enabled is False
    assert revoked.wipe_required is True
    with pytest.raises(VoiceFeatureDisabled):
        store.assert_enabled_for_processing()


@pytest.mark.unit
def test_privacy_enabled_requires_consent_at() -> None:
    with pytest.raises((SpeakerProfileContractError, ValidationError)):
        from transcriptx.core.speaker_profiles.voice.models import (
            VoicePrivacySettingsV1,
        )

        VoicePrivacySettingsV1(
            enabled=True,
            privacy_notice_version=PRIVACY_NOTICE_VERSION,
        )


@pytest.mark.unit
def test_link_provenance_rejects_raw_dict() -> None:
    with pytest.raises(SpeakerProfileContractError):
        coerce_link_provenance({"link_method": "manual"})  # type: ignore[arg-type]


@pytest.mark.unit
def test_suggestion_assisted_requires_digest() -> None:
    with pytest.raises((SpeakerProfileContractError, ValidationError)):
        LinkProvenanceV1(link_method="suggestion_assisted", suggestion_id="s1")
    ok = LinkProvenanceV1(
        link_method="suggestion_assisted",
        suggestion_id="s1",
        suggestion_digest="abc",
    )
    assert ok.to_storage_dict()["suggestion_digest"] == "abc"


@pytest.mark.unit
def test_assert_safe_relpath_rejects_absolute_and_traversal() -> None:
    assert assert_safe_relpath("voice/privacy.voice_settings.json") == (
        "voice/privacy.voice_settings.json"
    )
    with pytest.raises(SpeakerProfileContractError):
        assert_safe_relpath("/etc/passwd")
    with pytest.raises(SpeakerProfileContractError):
        assert_safe_relpath("../escape")
    with pytest.raises(SpeakerProfileContractError):
        assert_safe_relpath("voice/../../etc/passwd")
    with pytest.raises(SpeakerProfileContractError):
        assert_safe_relpath("C:/windows/system32")


@pytest.mark.unit
def test_assert_relpath_under_root(tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    path = assert_relpath_under_root("voice/x.json", root)
    assert path == (root / "voice" / "x.json").resolve()


@pytest.mark.unit
def test_cache_signal_accepts_speaker_voice_scope() -> None:
    signal = CacheInvalidationSignal(scopes=("speaker_voice",))
    assert "speaker_voice" in signal.scopes


@pytest.mark.unit
def test_extra_forbid_on_provenance() -> None:
    with pytest.raises(ValidationError):
        LinkProvenanceV1(link_method="manual", unexpected="x")  # type: ignore[call-arg]
