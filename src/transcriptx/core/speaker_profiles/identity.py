"""Managed transcript IDs, occurrence keys, and link file keys."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from transcriptx.core.speaker_profiles.errors import (
    SpeakerKeyCollisionError,
    SpeakerProfileContractError,
)
from transcriptx.core.speaker_profiles.versioning import OCCURRENCE_KEY_PREFIX
from transcriptx.io.speaker_map_resolver import normalize_diarized_id


def canonicalize_managed_transcript_id(import_id: str | uuid.UUID) -> str:
    """Return lowercase hyphenated UUID string from import_id.

    Frozen rule: ``managed_transcript_id = str(uuid.UUID(import_id))``.
    Rejects non-UUID import ids.
    """
    try:
        if isinstance(import_id, uuid.UUID):
            value = import_id
        else:
            value = uuid.UUID(str(import_id).strip())
    except (ValueError, AttributeError, TypeError) as exc:
        raise SpeakerProfileContractError(
            f"import_id must be a UUID; got {import_id!r}"
        ) from exc
    return str(value)


def local_speaker_key_from_raw(raw_speaker: Any) -> str:
    """Normalise a raw segment speaker to the occurrence local_speaker_key."""
    key = normalize_diarized_id(raw_speaker)
    if not key:
        raise SpeakerProfileContractError("local_speaker_key must be non-empty")
    return key


def occurrence_key_payload(
    managed_transcript_id: str, local_speaker_key: str
) -> list[str]:
    """Canonical JSON array payload for occurrence key hashing."""
    mt_id = canonicalize_managed_transcript_id(managed_transcript_id)
    speaker_key = str(local_speaker_key).strip()
    if not speaker_key:
        raise SpeakerProfileContractError("local_speaker_key must be non-empty")
    return [OCCURRENCE_KEY_PREFIX, mt_id, speaker_key]


def link_file_key(managed_transcript_id: str, local_speaker_key: str) -> str:
    """SHA-256 hex of UTF-8 canonical JSON occurrence key."""
    payload = occurrence_key_payload(managed_transcript_id, local_speaker_key)
    encoded = json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def detect_speaker_key_collisions(
    raw_speakers: list[Any],
) -> dict[str, list[str]]:
    """Map normalised keys to distinct raw forms that collide.

    Returns only keys with more than one distinct raw string representation
    after stripping (collision set). Empty dict means no collisions.
    """
    buckets: dict[str, set[str]] = {}
    for raw in raw_speakers:
        if raw is None:
            continue
        raw_text = str(raw).strip()
        if not raw_text:
            continue
        key = normalize_diarized_id(raw)
        if not key:
            continue
        buckets.setdefault(key, set()).add(raw_text)
    return {key: sorted(raws) for key, raws in buckets.items() if len(raws) > 1}


def assert_no_speaker_key_collision(raw_speakers: list[Any]) -> None:
    """Raise SpeakerKeyCollisionError when distinct raws collapse to one key."""
    collisions = detect_speaker_key_collisions(raw_speakers)
    if collisions:
        raise SpeakerKeyCollisionError(
            f"distinct raw speakers collapse to normalised keys: {collisions}"
        )
