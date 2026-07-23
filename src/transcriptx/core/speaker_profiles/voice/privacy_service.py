"""Journalled privacy enable / revoke (sole consent authority file)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from transcriptx.core.speaker_profiles.layout import speaker_profiles_project_lock
from transcriptx.core.speaker_profiles.operations import (
    OperationEngine,
    PlannedWrite,
    relative_event_path,
    relative_voice_privacy_path,
)
from transcriptx.core.speaker_profiles.signals import CacheInvalidationSignal
from transcriptx.core.speaker_profiles.store_io import dumps_model, ensure_layout, utc_now_iso
from transcriptx.core.speaker_profiles.voice.activation import ActivationBarrier
from transcriptx.core.speaker_profiles.voice.models import VoicePrivacySettingsV1
from transcriptx.core.speaker_profiles.voice.privacy import (
    PRIVACY_NOTICE_VERSION,
    VoicePrivacyStore,
)
from transcriptx.core.speaker_profiles.voice.wipe import VoiceWipeService
from transcriptx.core.utils.paths import PATHS


class VoicePrivacyService:
    """Journalled writes to ``privacy.voice_settings.json``."""

    def __init__(self, root: Path | None = None, state_dir: Path | None = None) -> None:
        self.root = Path(root) if root is not None else PATHS.speaker_profiles_dir
        self.state_dir = Path(state_dir) if state_dir is not None else PATHS.state_dir
        self.store = VoicePrivacyStore(self.root)
        self.engine = OperationEngine(self.root)
        self.barrier = ActivationBarrier(self.root)

    def enable(
        self,
        *,
        operation_idempotency_key: str,
        actor: str = "user",
        require_feature_gate: bool = True,
    ) -> VoicePrivacySettingsV1:
        if require_feature_gate:
            self.barrier.assert_settings_enablement_allowed()
        ensure_layout(self.root)
        with speaker_profiles_project_lock(self.state_dir):
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self.store.read()
            settings = VoicePrivacySettingsV1(
                enabled=True,
                consent_at=utc_now_iso(),
                consent_actor=actor,
                privacy_notice_version=PRIVACY_NOTICE_VERSION,
                revoked_at=None,
                wipe_required=False,
            )
            event_id = str(uuid4())
            from transcriptx.core.speaker_profiles.models import SpeakerProfileEventV1

            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="voice_privacy_enabled",
                created_at=utc_now_iso(),
                actor=actor,
                payload={"privacy_notice_version": PRIVACY_NOTICE_VERSION},
            )
            self.engine.run(
                op_type="voice_privacy_enable",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_voice_privacy_path(),
                        data=dumps_model(settings),
                    ),
                    PlannedWrite(
                        relpath=relative_event_path(event_id),
                        data=dumps_model(event),
                    ),
                ],
                deletes=[],
                receipt_extra={"scopes": ["speaker_voice"], "event_ids": [event_id]},
            )
            return settings

    def revoke(
        self,
        *,
        operation_idempotency_key: str,
        actor: str = "user",
        run_wipe: bool = True,
    ) -> tuple[VoicePrivacySettingsV1, CacheInvalidationSignal]:
        """Disable, mark wipe_required, then run bounded wipe and clear the flag."""
        ensure_layout(self.root)
        with speaker_profiles_project_lock(self.state_dir):
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self.store.read(), CacheInvalidationSignal(
                    scopes=("speaker_voice",)
                )
            settings = VoicePrivacySettingsV1(
                enabled=False,
                consent_at=None,
                consent_actor=None,
                privacy_notice_version=PRIVACY_NOTICE_VERSION,
                revoked_at=utc_now_iso(),
                wipe_required=True,
            )
            event_id = str(uuid4())
            from transcriptx.core.speaker_profiles.models import SpeakerProfileEventV1

            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="voice_privacy_revoked",
                created_at=utc_now_iso(),
                actor=actor,
                payload={"wipe_required": True},
            )
            self.engine.run(
                op_type="voice_privacy_revoke",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_voice_privacy_path(),
                        data=dumps_model(settings),
                    ),
                    PlannedWrite(
                        relpath=relative_event_path(event_id),
                        data=dumps_model(event),
                    ),
                ],
                deletes=[],
                receipt_extra={"scopes": ["speaker_voice"], "event_ids": [event_id]},
            )

        if run_wipe:
            VoiceWipeService(root=self.root, state_dir=self.state_dir).wipe_until_complete(
                base_idempotency_key=f"{operation_idempotency_key}:wipe",
                include_privacy=False,
            )
            self.clear_wipe_required(
                operation_idempotency_key=f"{operation_idempotency_key}:wipe_cleared",
                actor=actor,
            )

        return self.store.read(), CacheInvalidationSignal(scopes=("speaker_voice",))

    def clear_wipe_required(
        self,
        *,
        operation_idempotency_key: str,
        actor: str = "system",
    ) -> VoicePrivacySettingsV1:
        """Clear wipe_required after a successful bounded wipe."""
        ensure_layout(self.root)
        with speaker_profiles_project_lock(self.state_dir):
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self.store.read()
            current = self.store.read()
            settings = current.model_copy(update={"wipe_required": False})
            event_id = str(uuid4())
            from transcriptx.core.speaker_profiles.models import SpeakerProfileEventV1

            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="voice_wipe_required_cleared",
                created_at=utc_now_iso(),
                actor=actor,
                payload={},
            )
            self.engine.run(
                op_type="voice_wipe_required_cleared",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_voice_privacy_path(),
                        data=dumps_model(settings),
                    ),
                    PlannedWrite(
                        relpath=relative_event_path(event_id),
                        data=dumps_model(event),
                    ),
                ],
                deletes=[],
                receipt_extra={"scopes": ["speaker_voice"], "event_ids": [event_id]},
            )
            return settings
