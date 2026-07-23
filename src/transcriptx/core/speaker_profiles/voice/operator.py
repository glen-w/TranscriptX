"""Durable operator knobs for voice enrolment (separate from privacy consent)."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.speaker_profiles.path_safety import (
    assert_operation_path_under_root,
    assert_safe_relpath,
)
from transcriptx.core.speaker_profiles.voice.models import VoiceOperatorSettingsV1
from transcriptx.core.speaker_profiles.voice.versioning import (
    DEFAULT_BOOTSTRAP_MAX_LINKS,
    OPERATOR_SETTINGS_FILENAME,
    VOICE_SUBTREE,
)
from transcriptx.io.atomic_json import strict_json_dumps, write_bytes_atomic


def default_operator_settings() -> VoiceOperatorSettingsV1:
    """Missing-file defaults (bootstrap link cap, etc.)."""
    return VoiceOperatorSettingsV1(bootstrap_max_links=DEFAULT_BOOTSTRAP_MAX_LINKS)


def operator_settings_relpath() -> str:
    return f"{VOICE_SUBTREE}/{OPERATOR_SETTINGS_FILENAME}"


class VoiceOperatorStore:
    """Read/write ``operator.voice_settings.json`` under speaker_profiles_dir."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path(self) -> Path:
        rel = operator_settings_relpath()
        assert_safe_relpath(rel, what="voice operator settings")
        return assert_operation_path_under_root(
            self.root / rel, self.root, what="voice operator settings"
        )

    def read(self) -> VoiceOperatorSettingsV1:
        path = self.path()
        if not path.exists():
            return default_operator_settings()
        raw = json.loads(path.read_text(encoding="utf-8"))
        return VoiceOperatorSettingsV1.model_validate(raw)

    def write_atomic(self, settings: VoiceOperatorSettingsV1) -> None:
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = strict_json_dumps(
            settings.model_dump(mode="python"), indent=2
        ).encode("utf-8")
        write_bytes_atomic(path, payload)
