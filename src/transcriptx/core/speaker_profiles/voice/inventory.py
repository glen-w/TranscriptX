"""Read-only inventory helpers for Speakers voice UI."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from transcriptx.core.utils.paths import PATHS


@dataclass(frozen=True)
class VoiceSampleSummary:
    sample_id: str
    profile_id: str
    trust_level: str
    eligibility_state: str
    managed_transcript_id: str
    local_speaker_key: str


def list_samples_for_profile(
    profile_id: str, *, root: Path | None = None
) -> list[VoiceSampleSummary]:
    root = Path(root) if root is not None else PATHS.speaker_profiles_dir
    samples_dir = root / "voice" / "samples"
    if not samples_dir.is_dir():
        return []
    out: list[VoiceSampleSummary] = []
    for path in sorted(samples_dir.glob("*.voice_sample.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("profile_id") != profile_id:
            continue
        out.append(
            VoiceSampleSummary(
                sample_id=str(payload.get("sample_id") or path.name.split(".")[0]),
                profile_id=profile_id,
                trust_level=str(payload.get("trust_level") or ""),
                eligibility_state=str(payload.get("eligibility_state") or ""),
                managed_transcript_id=str(payload.get("managed_transcript_id") or ""),
                local_speaker_key=str(payload.get("local_speaker_key") or ""),
            )
        )
    return out
