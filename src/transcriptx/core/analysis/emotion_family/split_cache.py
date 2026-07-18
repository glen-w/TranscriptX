"""
Split cache layers for emotion-family modules (locked contract).

Three identity layers — never a single monolith:

| Layer | Key inputs | Stores |
|-------|-----------|--------|
| Inference | inference compatibility fingerprint + text source identity | per-segment score rows (no speaker/timeline/threshold) |
| Aggregation | inference generation id + speaker digest + timeline digest + aggregation semantics + settings (thresholds/caps) | speaker aggregates / timelines |
| Projection / presentation | artifact_generation_id + schema/semantics + display fingerprint | not cached; recomputed from canonical |

Speaker or timing edits must never return stale aggregates but must not force
re-scoring; text or analytical-policy changes bust the inference layer.
Threshold-only changes bust aggregation only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from transcriptx.core.analysis.emotion_family.canonical_hash import canonical_json_hash
from transcriptx.core.analysis.emotion_family.safe_ids import (
    assert_path_under_root,
    assert_safe_token,
)
from transcriptx.io.atomic_json import write_json_atomic

INFERENCE_CACHE_VERSION = "emotion_family_inference_cache_v3"
AGGREGATION_CACHE_VERSION = "emotion_family_aggregation_cache_v3"


def inference_cache_key(
    *,
    compatibility_fingerprint: str,
    text_source_digest: str,
) -> str:
    return canonical_json_hash(
        {
            "layer": "inference",
            "version": INFERENCE_CACHE_VERSION,
            "compatibility_fingerprint": compatibility_fingerprint,
            "text_source_digest": text_source_digest,
        }
    )


def aggregation_settings_digest(settings: Mapping[str, Any] | None) -> str:
    """Hash aggregation-affecting settings for the aggregation cache key."""
    return canonical_json_hash(dict(settings or {}))


def aggregation_cache_key(
    *,
    inference_generation_id: str,
    speaker_identity_digest: str,
    timeline_identity_digest: str,
    aggregation_semantics_version: str,
    aggregation_settings: Mapping[str, Any] | None = None,
) -> str:
    return canonical_json_hash(
        {
            "layer": "aggregation",
            "version": AGGREGATION_CACHE_VERSION,
            "inference_generation_id": inference_generation_id,
            "speaker_identity_digest": speaker_identity_digest,
            "timeline_identity_digest": timeline_identity_digest,
            "aggregation_semantics_version": aggregation_semantics_version,
            "aggregation_settings_digest": aggregation_settings_digest(
                aggregation_settings
            ),
        }
    )


def module_cache_fingerprint(*, inference_key: str, aggregation_key: str) -> str:
    """Coarse whole-module fingerprint; never used for split-layer lookups."""
    return canonical_json_hash(
        {"inference_key": inference_key, "aggregation_key": aggregation_key}
    )


def default_inference_cache_root(module_id: str) -> Path:
    from transcriptx.core.utils.paths import PATHS

    assert_safe_token(module_id, what="module_id")
    return PATHS.data_dir / "cache" / "emotion_family" / module_id


def default_aggregation_cache_root(module_id: str) -> Path:
    from transcriptx.core.utils.paths import PATHS

    assert_safe_token(module_id, what="module_id")
    return PATHS.data_dir / "cache" / "emotion_family" / module_id / "aggregation"


class InferenceCacheStore:
    """
    Persistent inference-layer cache: key → per-segment score rows.

    Entries must not contain speaker or timeline data — those belong to the
    aggregation layer. Rows are keyed by segment_id.

    Payload stamps a stable ``inference_generation_id`` (original scoring
    attempt). Callers must never treat it as ``artifact_generation_id``.
    Old cache versions are rejected without field aliasing.
    """

    def __init__(self, root: Path | str):
        self.root = Path(root)

    def _entry_path(self, key: str) -> Path:
        safe_key = assert_safe_token(key, what="cache_key") if False else key
        # Cache keys are hex digests from canonical_json_hash (64 hex chars).
        if not (
            isinstance(safe_key, str)
            and 16 <= len(safe_key) <= 128
            and all(c.isalnum() or c in "._-" for c in safe_key)
        ):
            raise ValueError(f"unsafe cache key: {key!r}")
        path = self.root / f"{safe_key}.json"
        self.root.mkdir(parents=True, exist_ok=True)
        assert_path_under_root(path, self.root)
        return path

    def load(self, key: str) -> dict[str, Any] | None:
        path = self._entry_path(key)
        if not path.is_file():
            return None
        try:
            import json

            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError):
            return None
        if payload.get("version") != INFERENCE_CACHE_VERSION:
            return None
        if not str(payload.get("inference_generation_id") or "").strip():
            return None
        rows = payload.get("rows_by_segment")
        if not isinstance(rows, dict):
            return None
        return payload

    def store(
        self,
        key: str,
        *,
        inference_generation_id: str,
        rows_by_segment: Mapping[str, Mapping[str, Any]],
    ) -> None:
        if not str(inference_generation_id or "").strip():
            raise ValueError("inference_generation_id required for inference cache")
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": INFERENCE_CACHE_VERSION,
            "inference_generation_id": inference_generation_id,
            "rows_by_segment": {k: dict(v) for k, v in rows_by_segment.items()},
        }
        write_json_atomic(self._entry_path(key), payload, indent=None)


class AggregationCacheStore:
    """
    Persistent aggregation-layer cache: key → speaker/timeline/summary payload.

    Keyed by inference generation id + speaker + timeline digests + settings
    so speaker or timing edits bust aggregates without forcing re-scoring.
    """

    def __init__(self, root: Path | str):
        self.root = Path(root)

    def _entry_path(self, key: str) -> Path:
        if not (
            isinstance(key, str)
            and 16 <= len(key) <= 128
            and all(c.isalnum() or c in "._-" for c in key)
        ):
            raise ValueError(f"unsafe cache key: {key!r}")
        path = self.root / f"{key}.json"
        self.root.mkdir(parents=True, exist_ok=True)
        assert_path_under_root(path, self.root)
        return path

    def load(self, key: str) -> dict[str, Any] | None:
        path = self._entry_path(key)
        if not path.is_file():
            return None
        try:
            import json

            with path.open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError):
            return None
        if payload.get("version") != AGGREGATION_CACHE_VERSION:
            return None
        return payload

    def store(
        self,
        key: str,
        *,
        inference_generation_id: str,
        aggregates: Mapping[str, Any],
    ) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": AGGREGATION_CACHE_VERSION,
            "inference_generation_id": inference_generation_id,
            "aggregates": dict(aggregates),
        }
        write_json_atomic(self._entry_path(key), payload, indent=None)
