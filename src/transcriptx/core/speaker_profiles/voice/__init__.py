"""Voice matching (speaker-profile voice phase) — evidence and suggestions.

Confirmed ``SpeakerProfileLink`` records remain the sole identity authority.
Voice artefacts are suggestive evidence only. Production analyse / enrol /
accept / Settings enablement stay behind ``ActivationBarrier`` until the
lifecycle gate is flipped (Stage 8).
"""

from __future__ import annotations

from transcriptx.core.speaker_profiles.voice.activation import (
    ActivationBarrier,
    ActivationStatus,
)
from transcriptx.core.speaker_profiles.voice.errors import (
    PrivacyConsentRequired,
    VoiceFeatureDisabled,
    VoiceFeatureGateClosed,
)
from transcriptx.core.speaker_profiles.voice.evidence import VoiceEvidenceService
from transcriptx.core.speaker_profiles.voice.export_exclude import (
    filter_speaker_profiles_export_paths,
    is_voice_excluded_relpath,
)
from transcriptx.core.speaker_profiles.voice.privacy import (
    PRIVACY_NOTICE_VERSION,
    VoicePrivacyStore,
    default_privacy_settings,
)
from transcriptx.core.speaker_profiles.voice.versioning import (
    ACTIVE_GENERATION_FILENAME,
    FEATURE_GATE_COMPLETE,
    PRIVACY_SETTINGS_FILENAME,
    PRIVACY_SETTINGS_SCHEMA_ID,
    VOICE_SUBTREE,
)

__all__ = [
    "ACTIVE_GENERATION_FILENAME",
    "ActivationBarrier",
    "ActivationStatus",
    "FEATURE_GATE_COMPLETE",
    "PRIVACY_NOTICE_VERSION",
    "PRIVACY_SETTINGS_FILENAME",
    "PRIVACY_SETTINGS_SCHEMA_ID",
    "PrivacyConsentRequired",
    "VOICE_SUBTREE",
    "VoiceEvidenceService",
    "VoiceFeatureDisabled",
    "VoiceFeatureGateClosed",
    "VoicePrivacyStore",
    "default_privacy_settings",
    "filter_speaker_profiles_export_paths",
    "is_voice_excluded_relpath",
]
