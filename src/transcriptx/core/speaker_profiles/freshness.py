"""Shared profile freshness token builder for aggregates and analytics pack."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.aggregates import AppearanceRow
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1


def _date_token(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _metrics_digest(row: AppearanceRow) -> dict[str, Any]:
    m = row.metrics
    return {
        "words": int(m.words),
        "turns": int(m.turns),
        "duration_seconds": m.duration_seconds,
        "timing_valid_turn_count": int(m.timing_valid_turn_count),
        "wpm": m.wpm,
    }


def build_profile_freshness_token(
    *,
    profile: SpeakerProfileV1,
    appearance_rows: Sequence[AppearanceRow],
    transcript_denominators: Mapping[str, float] | None = None,
    occurrence_fingerprints: Mapping[str, str] | None = None,
) -> str:
    """SHA-256 hex token; any listed input change must change the token."""
    dens = transcript_denominators or {}
    fps = occurrence_fingerprints or {}
    referenced_tids = sorted({r.managed_transcript_id for r in appearance_rows})
    payload = {
        "profile_id": profile.profile_id,
        "status": profile.status,
        "merged_into_profile_id": profile.merged_into_profile_id,
        "updated_at": profile.updated_at,
        "display_name": profile.display_name,
        "appearances": [
            {
                "link_id": r.link_id,
                "managed_transcript_id": r.managed_transcript_id,
                "local_speaker_key": r.local_speaker_key,
                "occurrence_fingerprint": fps.get(r.link_id, ""),
                "flag": r.flag,
                "ignored": bool(r.ignored),
                "appearance_date": _date_token(r.appearance_date),
                "metrics": _metrics_digest(r),
            }
            for r in sorted(appearance_rows, key=lambda x: x.link_id)
        ],
        "denominators": {tid: dens.get(tid) for tid in referenced_tids if tid in dens},
    }
    return hashlib.sha256(
        json.dumps(
            payload, separators=(",", ":"), sort_keys=True, allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
