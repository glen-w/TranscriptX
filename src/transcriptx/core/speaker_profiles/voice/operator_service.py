"""Journalled updates to voice operator settings."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from transcriptx.core.speaker_profiles.layout import speaker_profiles_project_lock
from transcriptx.core.speaker_profiles.operations import (
    OperationEngine,
    PlannedWrite,
    relative_event_path,
    relative_voice_operator_path,
)
from transcriptx.core.speaker_profiles.store_io import dumps_model, ensure_layout, utc_now_iso
from transcriptx.core.speaker_profiles.voice.models import VoiceOperatorSettingsV1
from transcriptx.core.speaker_profiles.voice.operator import VoiceOperatorStore
from transcriptx.core.utils.paths import PATHS


class VoiceOperatorService:
    """Journalled writes to ``operator.voice_settings.json``."""

    def __init__(self, root: Path | None = None, state_dir: Path | None = None) -> None:
        self.root = Path(root) if root is not None else PATHS.speaker_profiles_dir
        self.state_dir = Path(state_dir) if state_dir is not None else PATHS.state_dir
        self.store = VoiceOperatorStore(self.root)
        self.engine = OperationEngine(self.root)

    def update_bootstrap_max_links(
        self,
        *,
        operation_idempotency_key: str,
        bootstrap_max_links: int,
        actor: str = "user",
    ) -> VoiceOperatorSettingsV1:
        ensure_layout(self.root)
        with speaker_profiles_project_lock(self.state_dir):
            replay = self.engine.find_complete(operation_idempotency_key)
            if replay is not None:
                return self.store.read()
            settings = VoiceOperatorSettingsV1(
                bootstrap_max_links=bootstrap_max_links,
                updated_at=utc_now_iso(),
                updated_by=actor,
            )
            event_id = str(uuid4())
            from transcriptx.core.speaker_profiles.models import SpeakerProfileEventV1

            event = SpeakerProfileEventV1(
                event_id=event_id,
                idempotency_id=event_id,
                operation_idempotency_key=operation_idempotency_key,
                event_type="voice_operator_settings_updated",
                created_at=utc_now_iso(),
                actor=actor,
                payload={"bootstrap_max_links": bootstrap_max_links},
            )
            self.engine.run(
                op_type="voice_operator_settings_update",
                operation_idempotency_key=operation_idempotency_key,
                writes=[
                    PlannedWrite(
                        relpath=relative_voice_operator_path(),
                        data=dumps_model(settings),
                    ),
                    PlannedWrite(
                        relpath=relative_event_path(event_id),
                        data=dumps_model(event),
                    ),
                ],
                deletes=[],
                receipt_extra={
                    "scopes": ["speaker_voice"],
                    "event_ids": [event_id],
                    "bootstrap_max_links": bootstrap_max_links,
                },
            )
            return settings
