"""Sole privacy / consent authority for local voice matching."""

from __future__ import annotations

import json
import os
from pathlib import Path

from transcriptx.core.speaker_profiles.path_safety import (
    assert_operation_path_under_root,
    assert_safe_relpath,
)
from transcriptx.core.speaker_profiles.store_io import utc_now_iso
from transcriptx.core.speaker_profiles.voice.errors import (
    PrivacyConsentRequired,
    VoiceFeatureDisabled,
)
from transcriptx.core.speaker_profiles.voice.models import VoicePrivacySettingsV1
from transcriptx.core.speaker_profiles.voice.versioning import (
    PRIVACY_SETTINGS_FILENAME,
    VOICE_SUBTREE,
)
from transcriptx.io.atomic_json import strict_json_dumps, write_bytes_atomic

# Bump when user-facing privacy notice text changes → require re-consent.
PRIVACY_NOTICE_VERSION = "voice_privacy_notice.v2"

# Shown in Settings before enable / while enabled. Keep in sync with
# PRIVACY_NOTICE_VERSION (bump version when this text changes materially).
VOICE_PRIVACY_USER_NOTICE = (
    "Local voice matching stores speaker-identity embeddings and audio "
    "excerpts on this machine only (under speaker_profiles/voice). "
    "Embeddings can identify a speaker across transcripts. Nothing is "
    "uploaded unless you separately configure a remote model download. "
    "Revoking consent deletes enrolled samples, embeddings, and vectors; "
    "profiles and confirmed links are kept."
)

# Local/dev only: when privacy.voice_settings.json is absent, treat voice as
# enabled. Never overrides an existing settings file (sole authority).
_VOICE_PRIVACY_DEFAULT_ENABLED_ENV = "TRANSCRIPTX_VOICE_PRIVACY_DEFAULT_ENABLED"
_DEFAULT_ENABLED_CONSENT_AT = "1970-01-01T00:00:00Z"
_DEFAULT_ENABLED_CONSENT_ACTOR = "env:TRANSCRIPTX_VOICE_PRIVACY_DEFAULT_ENABLED"


def _env_default_enabled() -> bool:
    raw = os.environ.get(_VOICE_PRIVACY_DEFAULT_ENABLED_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def default_privacy_settings() -> VoicePrivacySettingsV1:
    """Return settings used when ``privacy.voice_settings.json`` is missing.

    Production fail-closed: disabled unless
    ``TRANSCRIPTX_VOICE_PRIVACY_DEFAULT_ENABLED`` is set (local/dev override).
    """
    if _env_default_enabled():
        return VoicePrivacySettingsV1(
            enabled=True,
            consent_at=_DEFAULT_ENABLED_CONSENT_AT,
            consent_actor=_DEFAULT_ENABLED_CONSENT_ACTOR,
            privacy_notice_version=PRIVACY_NOTICE_VERSION,
        )
    return VoicePrivacySettingsV1(
        enabled=False,
        privacy_notice_version=PRIVACY_NOTICE_VERSION,
    )


def privacy_settings_relpath() -> str:
    return f"{VOICE_SUBTREE}/{PRIVACY_SETTINGS_FILENAME}"


class VoicePrivacyStore:
    """Read/write ``privacy.voice_settings.json`` under speaker_profiles_dir."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path(self) -> Path:
        rel = privacy_settings_relpath()
        assert_safe_relpath(rel, what="voice privacy settings")
        return assert_operation_path_under_root(
            self.root / rel, self.root, what="voice privacy settings"
        )

    def read(self) -> VoicePrivacySettingsV1:
        path = self.path()
        if not path.exists():
            return default_privacy_settings()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return VoicePrivacySettingsV1.model_validate(raw)

    def write_atomic(self, settings: VoicePrivacySettingsV1) -> None:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = strict_json_dumps(
            settings.model_dump(mode="python"), indent=2
        ).encode("utf-8")
        write_bytes_atomic(path, payload)

    def assert_enabled_for_processing(self) -> VoicePrivacySettingsV1:
        """Fail closed unless enabled and notice version is current."""
        settings = self.read()
        if not settings.enabled:
            raise VoiceFeatureDisabled("local voice matching is disabled")
        if settings.privacy_notice_version != PRIVACY_NOTICE_VERSION:
            raise PrivacyConsentRequired(
                "privacy notice version outdated; re-consent required"
            )
        if settings.wipe_required:
            raise VoiceFeatureDisabled(
                "voice wipe required after revocation; processing blocked"
            )
        return settings

    def enable(
        self,
        *,
        actor: str = "user",
        notice_version: str | None = None,
    ) -> VoicePrivacySettingsV1:
        """Record consent and enable. Caller must hold project lock + journal."""
        notice = notice_version or PRIVACY_NOTICE_VERSION
        if notice != PRIVACY_NOTICE_VERSION:
            raise PrivacyConsentRequired(
                f"cannot consent to unknown notice version {notice!r}"
            )
        settings = VoicePrivacySettingsV1(
            enabled=True,
            consent_at=utc_now_iso(),
            consent_actor=actor,
            privacy_notice_version=PRIVACY_NOTICE_VERSION,
            revoked_at=None,
            wipe_required=False,
        )
        self.write_atomic(settings)
        return settings

    def revoke(self, *, actor: str = "user") -> VoicePrivacySettingsV1:
        """Disable and mark wipe required. Caller journals + runs bounded wipe."""
        _ = actor
        settings = VoicePrivacySettingsV1(
            enabled=False,
            consent_at=None,
            consent_actor=None,
            privacy_notice_version=PRIVACY_NOTICE_VERSION,
            revoked_at=utc_now_iso(),
            wipe_required=True,
        )
        self.write_atomic(settings)
        return settings
