"""Per-transcript identify artefact (review, not identity authority)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from transcriptx.core.speaker_profiles.identify.models import (
    FusedDecision,
    IdentifyResult,
    SpeakerApplyResult,
)
from transcriptx.core.speaker_profiles.layout import speaker_profiles_dir
from transcriptx.core.speaker_profiles.store_io import utc_now_iso
from transcriptx.io.atomic_json import write_json_atomic

ARTEFACT_SCHEMA_ID = "transcriptx.speaker_identify_artefact.v1"


def identify_artefact_path(
    managed_transcript_id: str, *, root: Path | None = None
) -> Path:
    base = Path(root) if root is not None else speaker_profiles_dir()
    return base / ".cache" / "identify" / f"{managed_transcript_id}.identify.v1.json"


def decision_to_dict(decision: FusedDecision) -> dict[str, Any]:
    return {
        "local_speaker_key": decision.local_speaker_key,
        "action": decision.action,
        "skip_reason": decision.skip_reason,
        "display_name": decision.display_name,
        "profile_id": decision.profile_id,
        "channels": list(decision.channels),
        "confidence": decision.confidence,
        "evidence": dict(decision.evidence),
    }


def apply_to_dict(row: SpeakerApplyResult) -> dict[str, Any]:
    return {
        "local_speaker_key": row.local_speaker_key,
        "named": row.named,
        "linked": row.linked,
        "skipped_name_reason": row.skipped_name_reason,
        "skipped_link_reason": row.skipped_link_reason,
        "display_name": row.display_name,
        "profile_id": row.profile_id,
        "error": row.error,
    }


def write_identify_artefact(
    result: IdentifyResult, *, root: Path | None = None
) -> Path | None:
    if not result.managed_transcript_id:
        return None
    path = identify_artefact_path(result.managed_transcript_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_id": ARTEFACT_SCHEMA_ID,
        "created_at": utc_now_iso(),
        "transcript_path": result.transcript_path,
        "managed_transcript_id": result.managed_transcript_id,
        "auto_name": result.auto_name,
        "auto_link": result.auto_link,
        "dry_run": result.dry_run,
        "named_count": result.named_count,
        "linked_count": result.linked_count,
        "skipped_count": result.skipped_count,
        "error": result.error,
        "decisions": [decision_to_dict(d) for d in result.decisions],
        "applied": [apply_to_dict(a) for a in result.applied],
    }
    write_json_atomic(path, payload, indent=2)
    return path


def load_identify_artefact(
    managed_transcript_id: str, *, root: Path | None = None
) -> dict[str, Any] | None:
    path = identify_artefact_path(managed_transcript_id, root=root)
    if not path.is_file():
        return None
    import json

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def artefact_row_for_speaker(
    artefact: dict[str, Any] | None, local_speaker_key: str
) -> dict[str, Any] | None:
    if not artefact:
        return None
    for row in artefact.get("applied") or []:
        if isinstance(row, dict) and row.get("local_speaker_key") == local_speaker_key:
            return row
    for row in artefact.get("decisions") or []:
        if isinstance(row, dict) and row.get("local_speaker_key") == local_speaker_key:
            return row
    return None
