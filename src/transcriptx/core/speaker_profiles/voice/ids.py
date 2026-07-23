"""Deterministic voice sample / embedding identity helpers."""

from __future__ import annotations

import hashlib
import json

from transcriptx.core.speaker_profiles.voice.versioning import (
    EMBEDDING_ID_PREFIX,
    EMBEDDING_SCHEMA_VERSION,
    PREPROCESSING_POLICY_ID,
    QUALITY_POLICY_ID,
    SAMPLE_ID_PREFIX,
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def compute_sample_id(
    *,
    occurrence_fingerprint: str,
    audio_content_sha256: str,
    clip_start_us: int,
    clip_end_us: int,
    model_generation_id: str,
    preprocessing_policy_id: str = PREPROCESSING_POLICY_ID,
    quality_policy_id: str = QUALITY_POLICY_ID,
) -> str:
    payload = _canonical_json(
        [
            SAMPLE_ID_PREFIX,
            occurrence_fingerprint,
            audio_content_sha256,
            clip_start_us,
            clip_end_us,
            model_generation_id,
            preprocessing_policy_id,
            quality_policy_id,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_embedding_id(
    *,
    sample_id: str,
    model_generation_id: str,
    embedding_schema_version: str = EMBEDDING_SCHEMA_VERSION,
) -> str:
    payload = _canonical_json(
        [
            EMBEDDING_ID_PREFIX,
            sample_id,
            model_generation_id,
            embedding_schema_version,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
