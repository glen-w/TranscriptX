"""Filesystem caches for query vectors and suggestions."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from transcriptx.core.speaker_profiles.path_safety import assert_safe_relpath
from transcriptx.core.speaker_profiles.voice.vectors import (
    encode_vector_npy_bytes,
    load_vector_npy,
)
from transcriptx.io.atomic_json import strict_json_dumps, write_bytes_atomic


def query_cache_key(
    *,
    occurrence_fingerprint: str,
    audio_content_sha256: str,
    model_generation_id: str,
    preprocessing_policy_id: str,
    quality_policy_id: str,
    ranges_us: list[tuple[int, int]],
) -> str:
    payload = json.dumps(
        [
            "voice_query_cache.v1",
            occurrence_fingerprint,
            audio_content_sha256,
            model_generation_id,
            preprocessing_policy_id,
            quality_policy_id,
            ranges_us,
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def suggestion_cache_key(
    *,
    occurrence_fingerprint: str,
    model_generation_id: str,
    threshold_policy_id: str,
    reference_corpus_digest: str,
) -> str:
    payload = json.dumps(
        [
            "voice_suggestion_cache.v1",
            occurrence_fingerprint,
            model_generation_id,
            threshold_policy_id,
            reference_corpus_digest,
        ],
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class VoiceQueryCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.base = self.root / ".cache" / "voice" / "query"

    def dir_for(self, key: str) -> Path:
        if "/" in key or ".." in key:
            from transcriptx.core.speaker_profiles.voice.errors import VoicePathError

            raise VoicePathError(f"bad query cache key: {key!r}")
        return self.base / key

    def write(
        self,
        key: str,
        *,
        meta: dict,
        vectors: list,
    ) -> None:
        d = self.dir_for(key)
        d.mkdir(parents=True, exist_ok=True)
        write_bytes_atomic(
            d / "meta.json",
            strict_json_dumps(meta, indent=2).encode("utf-8"),
        )
        for i, vec in enumerate(vectors):
            data, _ = encode_vector_npy_bytes(vec)
            write_bytes_atomic(d / f"vector_{i}.npy", data)

    def read(self, key: str) -> tuple[dict, list] | None:
        d = self.dir_for(key)
        meta_path = d / "meta.json"
        if not meta_path.is_file():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        vectors = []
        i = 0
        while True:
            vp = d / f"vector_{i}.npy"
            if not vp.is_file():
                break
            vectors.append(load_vector_npy(vp))
            i += 1
        if not vectors:
            return None
        return meta, vectors


class VoiceSuggestionCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.base = self.root / ".cache" / "voice" / "suggestions"

    def path_for(self, key: str) -> Path:
        assert_safe_relpath(f".cache/voice/suggestions/{key}.json")
        if "/" in key or ".." in key:
            from transcriptx.core.speaker_profiles.voice.errors import VoicePathError

            raise VoicePathError(f"bad suggestion cache key: {key!r}")
        return self.base / f"{key}.json"

    def write(self, key: str, payload: dict) -> None:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_bytes_atomic(
            path, strict_json_dumps(payload, indent=2).encode("utf-8")
        )

    def read(self, key: str) -> dict | None:
        path = self.path_for(key)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def invalidate_all(self) -> int:
        if not self.base.is_dir():
            return 0
        n = 0
        for p in self.base.glob("*.json"):
            p.unlink(missing_ok=True)
            n += 1
        return n
