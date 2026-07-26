"""Single activation barrier for voice matching UX and enrolment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.voice.errors import (
    PrivacyConsentRequired,
    VoiceFeatureDisabled,
    VoiceFeatureGateClosed,
)
from transcriptx.core.speaker_profiles.voice.privacy import (
    PRIVACY_NOTICE_VERSION,
    VoicePrivacyStore,
)
from transcriptx.core.speaker_profiles.voice.versioning import FEATURE_GATE_COMPLETE

ActivationBlockReason = Literal[
    "feature_gate_closed",
    "privacy_disabled",
    "privacy_consent_required",
    "privacy_settings_invalid",
    "wipe_required",
]


@dataclass(frozen=True)
class ActivationStatus:
    """Result of evaluating the single activation barrier."""

    allowed: bool
    feature_gate_complete: bool
    privacy_enabled: bool
    notice_current: bool
    wipe_required: bool
    block_reason: ActivationBlockReason | None = None
    detail: str | None = None


class ActivationBarrier:
    """Gate analyse / enrol / accept / Settings enablement.

    Production analyse/enrol/accept require ``FEATURE_GATE_COMPLETE`` and an
    enabled, current ``privacy.voice_settings.json``. Settings enablement is
    allowed once the feature gate is open; privacy remains the sole consent
    authority (no parallel config flag).
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._privacy = VoicePrivacyStore(self.root)

    def status(self) -> ActivationStatus:
        if not FEATURE_GATE_COMPLETE:
            return ActivationStatus(
                allowed=False,
                feature_gate_complete=False,
                privacy_enabled=False,
                notice_current=False,
                wipe_required=False,
                block_reason="feature_gate_closed",
                detail=(
                    "Voice matching is not available until lifecycle, recovery, "
                    "deletion, privacy, and integrity stages are complete."
                ),
            )

        try:
            settings = self._privacy.read()
        except (ValidationError, SpeakerProfileContractError, ValueError, OSError) as exc:
            # Refuse pre-epoch / corrupt privacy docs; do not crash Speakers UX.
            return ActivationStatus(
                allowed=False,
                feature_gate_complete=True,
                privacy_enabled=False,
                notice_current=False,
                wipe_required=False,
                block_reason="privacy_settings_invalid",
                detail=(
                    "privacy.voice_settings.json is incompatible or unreadable "
                    f"({exc}). Re-enable voice matching in Settings → Speakers "
                    "after removing or replacing the pre-epoch settings file."
                ),
            )
        notice_current = settings.privacy_notice_version == PRIVACY_NOTICE_VERSION
        if settings.wipe_required:
            return ActivationStatus(
                allowed=False,
                feature_gate_complete=True,
                privacy_enabled=False,
                notice_current=notice_current,
                wipe_required=True,
                block_reason="wipe_required",
                detail="Voice data wipe required after privacy revocation.",
            )
        if not settings.enabled:
            return ActivationStatus(
                allowed=False,
                feature_gate_complete=True,
                privacy_enabled=False,
                notice_current=notice_current,
                wipe_required=False,
                block_reason="privacy_disabled",
                detail="Local voice matching is disabled.",
            )
        if not notice_current:
            return ActivationStatus(
                allowed=False,
                feature_gate_complete=True,
                privacy_enabled=True,
                notice_current=False,
                wipe_required=False,
                block_reason="privacy_consent_required",
                detail="Privacy notice version outdated; re-consent required.",
            )
        return ActivationStatus(
            allowed=True,
            feature_gate_complete=True,
            privacy_enabled=True,
            notice_current=True,
            wipe_required=False,
            block_reason=None,
            detail=None,
        )

    def assert_processing_allowed(self) -> ActivationStatus:
        status = self.status()
        if status.allowed:
            return status
        if status.block_reason == "feature_gate_closed":
            raise VoiceFeatureGateClosed(status.detail or "feature gate closed")
        if status.block_reason == "privacy_consent_required":
            raise PrivacyConsentRequired(status.detail or "re-consent required")
        if status.block_reason == "privacy_settings_invalid":
            raise VoiceFeatureDisabled(
                status.detail or "privacy settings incompatible"
            )
        raise VoiceFeatureDisabled(status.detail or "voice matching disabled")

    def assert_settings_enablement_allowed(self) -> None:
        """Settings may offer enable only after the lifecycle feature gate opens."""
        if not FEATURE_GATE_COMPLETE:
            raise VoiceFeatureGateClosed(
                "Voice matching Settings enablement is not available yet."
            )
