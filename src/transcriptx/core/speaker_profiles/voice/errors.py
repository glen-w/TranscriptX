"""Typed outcomes / errors for the speaker-profile voice phase."""

from __future__ import annotations

from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError


class VoiceFeatureError(SpeakerProfileContractError):
    """Base for voice-phase failures."""


class VoiceFeatureGateClosed(VoiceFeatureError):
    """Lifecycle / integrity gate not yet complete (Stage 8)."""


class VoiceFeatureDisabled(VoiceFeatureError):
    """Privacy settings have voice matching disabled."""


class PrivacyConsentRequired(VoiceFeatureError):
    """Notice version outdated or consent missing; re-consent required."""


class VoicePathError(VoiceFeatureError):
    """Invalid voice relative path (absolute, traversal, or escape)."""
