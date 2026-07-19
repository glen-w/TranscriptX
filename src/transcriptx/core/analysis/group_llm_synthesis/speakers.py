"""Canonical speaker identity and collision-resistant artifact tokens."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from transcriptx.core.analysis.llm_support.filenames import safe_speaker_filename


@dataclass(frozen=True)
class SpeakerIdentity:
    canonical_speaker_id: str
    display_name: str
    artifact_token: str


def _short_hash(text: str, n: int = 12) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def resolve_speaker_canonical_id(
    *,
    canonical_speaker_id: str | None,
    raw_or_display: str | None,
    source_transcript_id: str,
    row_key_or_ordinal: str | int,
) -> tuple[str, str]:
    """Return (canonical_id, display_name)."""
    canon = str(canonical_speaker_id or "").strip()
    raw = str(raw_or_display or "").strip()
    if canon:
        return canon, (raw or canon)
    if raw:
        return f"unmapped:{_short_hash(raw)}", raw
    key = f"{source_transcript_id}|{row_key_or_ordinal}"
    return f"unknown:{_short_hash(key)}", "Unknown speaker"


def build_artifact_tokens(
    canonical_ids: list[str], display_names: list[str]
) -> dict[str, str]:
    """Map canonical_id → artifact_token with collision counters."""
    assert len(canonical_ids) == len(display_names)
    # Deterministic order by canonical id for counter assignment
    ordered = sorted(zip(canonical_ids, display_names), key=lambda x: x[0])
    used: dict[str, str] = {}
    token_owners: dict[str, str] = {}
    for canon, display in ordered:
        prefix = safe_speaker_filename(display or canon)[:40] or "speaker"
        base = f"{prefix}_{_short_hash(canon)}"
        token = base
        n = 2
        while token in token_owners and token_owners[token] != canon:
            token = f"{base}_{n}"
            n += 1
        token_owners[token] = canon
        used[canon] = token
    return used
