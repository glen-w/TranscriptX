"""Disposable Stage 9 reference corpus file index (no DB).

Rebuildable under ``.cache/voice/indexes/``, keyed by model generation + corpus
digest. Prefer this over a full embedding-tree scan when present and fresh.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from transcriptx.core.speaker_profiles.store_io import read_profile, utc_now_iso
from transcriptx.core.speaker_profiles.voice.models import VoiceEmbeddingV1
from transcriptx.core.speaker_profiles.voice.vectors import EXPECTED_DIM, load_vector_npy
from transcriptx.io.atomic_json import strict_json_dumps, write_bytes_atomic

MAX_REFS_PER_SOURCE_LINK = 5
INDEX_SCHEMA_ID = "transcriptx.voice_ref_index.v1"


def _digest_dirname(corpus_digest: str) -> str:
    # corpus_digest is typically "sha256:<hex>"; keep a stable short directory name.
    raw = corpus_digest.replace("sha256:", "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


@dataclass(frozen=True)
class RefIndexMeta:
    schema_id: str
    model_generation_id: str
    reference_corpus_digest: str
    embedding_ids: list[str]
    profile_ids: list[str]
    dimension: int
    row_count: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "model_generation_id": self.model_generation_id,
            "reference_corpus_digest": self.reference_corpus_digest,
            "embedding_ids": list(self.embedding_ids),
            "profile_ids": list(self.profile_ids),
            "dimension": self.dimension,
            "row_count": self.row_count,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RefIndexMeta:
        return cls(
            schema_id=str(data.get("schema_id") or INDEX_SCHEMA_ID),
            model_generation_id=str(data["model_generation_id"]),
            reference_corpus_digest=str(data["reference_corpus_digest"]),
            embedding_ids=list(data.get("embedding_ids") or []),
            profile_ids=list(data.get("profile_ids") or []),
            dimension=int(data.get("dimension") or EXPECTED_DIM),
            row_count=int(data.get("row_count") or 0),
            created_at=str(data.get("created_at") or ""),
        )


@dataclass(frozen=True)
class LoadedRefIndex:
    meta: RefIndexMeta
    matrix: np.ndarray  # (N, dim) float32

    def as_profile_refs(self) -> dict[str, list[np.ndarray]]:
        refs: dict[str, list[np.ndarray]] = {}
        for i, profile_id in enumerate(self.meta.profile_ids):
            refs.setdefault(profile_id, []).append(self.matrix[i])
        return refs


class VoiceRefIndexStore:
    """Filesystem matrix cache for eligible reference embeddings."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.base = self.root / ".cache" / "voice" / "indexes"

    def dir_for(self, *, model_generation_id: str, corpus_digest: str) -> Path:
        safe_gen = model_generation_id.replace("/", "_")[:64]
        return self.base / safe_gen / _digest_dirname(corpus_digest)

    def read(
        self, *, model_generation_id: str, corpus_digest: str
    ) -> LoadedRefIndex | None:
        d = self.dir_for(
            model_generation_id=model_generation_id, corpus_digest=corpus_digest
        )
        meta_path = d / "meta.json"
        matrix_path = d / "matrix.npy"
        if not meta_path.is_file() or not matrix_path.is_file():
            return None
        try:
            meta = RefIndexMeta.from_dict(
                json.loads(meta_path.read_text(encoding="utf-8"))
            )
        except Exception:
            return None
        if (
            meta.model_generation_id != model_generation_id
            or meta.reference_corpus_digest != corpus_digest
            or meta.schema_id != INDEX_SCHEMA_ID
        ):
            return None
        try:
            matrix = np.load(matrix_path, allow_pickle=False)
            matrix = np.asarray(matrix, dtype=np.float32)
        except Exception:
            return None
        if matrix.ndim != 2 or matrix.shape[0] != meta.row_count:
            return None
        if matrix.shape[1] != meta.dimension:
            return None
        if len(meta.embedding_ids) != meta.row_count or len(meta.profile_ids) != meta.row_count:
            return None
        return LoadedRefIndex(meta=meta, matrix=matrix)

    def write(
        self,
        *,
        model_generation_id: str,
        corpus_digest: str,
        embedding_ids: list[str],
        profile_ids: list[str],
        matrix: np.ndarray,
    ) -> RefIndexMeta:
        matrix = np.asarray(matrix, dtype=np.float32)
        if matrix.ndim != 2:
            raise ValueError("matrix must be 2-D")
        if matrix.shape[0] != len(embedding_ids) or matrix.shape[0] != len(profile_ids):
            raise ValueError("matrix rows must match id lists")
        meta = RefIndexMeta(
            schema_id=INDEX_SCHEMA_ID,
            model_generation_id=model_generation_id,
            reference_corpus_digest=corpus_digest,
            embedding_ids=list(embedding_ids),
            profile_ids=list(profile_ids),
            dimension=int(matrix.shape[1]),
            row_count=int(matrix.shape[0]),
            created_at=utc_now_iso(),
        )
        d = self.dir_for(
            model_generation_id=model_generation_id, corpus_digest=corpus_digest
        )
        d.mkdir(parents=True, exist_ok=True)
        write_bytes_atomic(
            d / "meta.json",
            strict_json_dumps(meta.to_dict(), indent=2).encode("utf-8"),
        )
        # Atomic-ish matrix replace via temp + rename.
        tmp = d / ".matrix.tmp.npy"
        np.save(tmp, matrix)
        tmp.replace(d / "matrix.npy")
        return meta


def list_eligible_embedding_ids(
    root: Path,
    *,
    model_generation_id: str,
    max_refs_per_source_link: int = MAX_REFS_PER_SOURCE_LINK,
) -> list[str]:
    """Metadata-only eligible embedding ids (no vector I/O) for corpus digest."""
    emb_dir = Path(root) / "voice" / "embeddings"
    ids: list[str] = []
    per_link_counts: dict[str, int] = {}
    if not emb_dir.is_dir():
        return ids
    for path in sorted(emb_dir.glob("*.voice_embedding.json")):
        try:
            emb = VoiceEmbeddingV1.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if emb.model_generation_id != model_generation_id:
            continue
        if emb.eligibility_state != "eligible":
            continue
        if emb.trust_level not in ("manual", "promoted"):
            continue
        link_cap_key = emb.source_link_id or emb.source_link_fingerprint
        used = per_link_counts.get(link_cap_key, 0)
        if used >= max_refs_per_source_link:
            continue
        profile = read_profile(emb.profile_id, root=root)
        if profile is None or profile.status != "active":
            continue
        vec_path = Path(root) / "voice" / "vectors" / f"{emb.embedding_id}.npy"
        if not vec_path.is_file():
            continue
        ids.append(emb.embedding_id)
        per_link_counts[link_cap_key] = used + 1
    return ids


def scan_eligible_ref_rows(
    root: Path,
    *,
    model_generation_id: str,
    max_refs_per_source_link: int = MAX_REFS_PER_SOURCE_LINK,
) -> tuple[list[str], list[str], np.ndarray]:
    """Tree scan of eligible refs → embedding_ids, profile_ids, matrix."""
    emb_dir = Path(root) / "voice" / "embeddings"
    embedding_ids: list[str] = []
    profile_ids: list[str] = []
    rows: list[np.ndarray] = []
    per_link_counts: dict[str, int] = {}
    if not emb_dir.is_dir():
        return [], [], np.zeros((0, EXPECTED_DIM), dtype=np.float32)
    for path in sorted(emb_dir.glob("*.voice_embedding.json")):
        try:
            emb = VoiceEmbeddingV1.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if emb.model_generation_id != model_generation_id:
            continue
        if emb.eligibility_state != "eligible":
            continue
        if emb.trust_level not in ("manual", "promoted"):
            continue
        link_cap_key = emb.source_link_id or emb.source_link_fingerprint
        used = per_link_counts.get(link_cap_key, 0)
        if used >= max_refs_per_source_link:
            continue
        profile = read_profile(emb.profile_id, root=root)
        if profile is None or profile.status != "active":
            continue
        vec_path = Path(root) / "voice" / "vectors" / f"{emb.embedding_id}.npy"
        if not vec_path.is_file():
            continue
        try:
            vec = load_vector_npy(vec_path, expected_sha256=emb.vector_sha256)
        except Exception:
            continue
        embedding_ids.append(emb.embedding_id)
        profile_ids.append(emb.profile_id)
        rows.append(np.asarray(vec, dtype=np.float32))
        per_link_counts[link_cap_key] = used + 1
    if not rows:
        return embedding_ids, profile_ids, np.zeros((0, EXPECTED_DIM), dtype=np.float32)
    return embedding_ids, profile_ids, np.stack(rows, axis=0)


def rebuild_ref_index(
    root: Path,
    *,
    model_generation_id: str,
    corpus_digest: str,
    store: VoiceRefIndexStore | None = None,
) -> LoadedRefIndex | None:
    """Rebuild index from tree; returns None on empty corpus or write failure."""
    store = store or VoiceRefIndexStore(root)
    emb_ids, profile_ids, matrix = scan_eligible_ref_rows(
        root, model_generation_id=model_generation_id
    )
    if not emb_ids:
        return None
    try:
        store.write(
            model_generation_id=model_generation_id,
            corpus_digest=corpus_digest,
            embedding_ids=emb_ids,
            profile_ids=profile_ids,
            matrix=matrix,
        )
    except Exception:
        return None
    loaded = store.read(
        model_generation_id=model_generation_id, corpus_digest=corpus_digest
    )
    return loaded


def load_or_rebuild_refs(
    root: Path,
    *,
    model_generation_id: str,
    corpus_digest: str,
    store: VoiceRefIndexStore | None = None,
) -> tuple[dict[str, list[np.ndarray]], list[str], str]:
    """Return profile_refs, embedding_ids, source (``index``|``scan``|``index_rebuild``).

    Never raises for cache failures — degrades to tree scan.
    """
    store = store or VoiceRefIndexStore(root)
    loaded = store.read(
        model_generation_id=model_generation_id, corpus_digest=corpus_digest
    )
    if loaded is not None:
        return loaded.as_profile_refs(), list(loaded.meta.embedding_ids), "index"

    rebuilt = rebuild_ref_index(
        root,
        model_generation_id=model_generation_id,
        corpus_digest=corpus_digest,
        store=store,
    )
    if rebuilt is not None:
        return rebuilt.as_profile_refs(), list(rebuilt.meta.embedding_ids), "index_rebuild"

    emb_ids, profile_ids, matrix = scan_eligible_ref_rows(
        root, model_generation_id=model_generation_id
    )
    refs: dict[str, list[np.ndarray]] = {}
    for i, pid in enumerate(profile_ids):
        refs.setdefault(pid, []).append(matrix[i])
    return refs, emb_ids, "scan"


def measure_scan_vs_index(
    *,
    profile_count: int = 500,
    refs_per_profile: int = 5,
    query_count: int = 3,
    dim: int = EXPECTED_DIM,
    seed: int = 0,
) -> dict[str, Any]:
    """Synthetic reference-env measurement (no disk tree required)."""
    rng = np.random.default_rng(seed)
    n = profile_count * refs_per_profile
    matrix = rng.standard_normal((n, dim), dtype=np.float32)
    # L2 normalize rows
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    matrix = matrix / norms
    queries = rng.standard_normal((query_count, dim), dtype=np.float32)
    qn = np.linalg.norm(queries, axis=1, keepdims=True)
    queries = queries / np.maximum(qn, 1e-12)

    t0 = time.perf_counter()
    # Simulate full scan: matmul queries @ matrix.T then reduce
    sims = queries @ matrix.T
    _ = float(sims.max())
    scan_ms = (time.perf_counter() - t0) * 1000.0

    # Index path is the same matmul once matrix is memory-resident; report load+matmul.
    t1 = time.perf_counter()
    loaded = np.asarray(matrix, dtype=np.float32).copy()
    sims2 = queries @ loaded.T
    _ = float(sims2.max())
    index_ms = (time.perf_counter() - t1) * 1000.0

    rss_est_mb = (n * dim * 4) / (1024 * 1024)
    return {
        "profile_count": profile_count,
        "refs_per_profile": refs_per_profile,
        "row_count": n,
        "dimension": dim,
        "query_count": query_count,
        "full_scan_matmul_ms": round(scan_ms, 3),
        "index_resident_matmul_ms": round(index_ms, 3),
        "estimated_matrix_rss_mb": round(rss_est_mb, 2),
        "advisory_full_scan_p95_ms": 500,
        "advisory_analyse_p95_ms": 2000,
        "advisory_peak_rss_mb": 512,
        "breaches_full_scan_advisory": scan_ms > 500,
        "note": (
            "Synthetic in-process matmul; tree I/O overhead is additional on scan "
            "path. File index avoids repeated .npy opens when digest-fresh."
        ),
    }
