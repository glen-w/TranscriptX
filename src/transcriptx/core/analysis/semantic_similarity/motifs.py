"""Motif export from eligible-row clusters (B14)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Sequence

import numpy as np

from transcriptx.core.analysis.semantic_similarity.intake import SegmentRow
from transcriptx.core.analysis.semantic_similarity.output import (
    EMBEDDING_SEMANTICS_VERSION,
    SCHEMA_VERSION,
    parse_schema_major,
)

NORM_TOLERANCE = 1e-3
TRUNCATION_LENGTH = 256
POOLING = "mean_masked"
NORMALIZATION = "l2"


def stable_segment_ref(row: SegmentRow) -> str:
    return f"{row.source_index}:{row.segment_id}"


def serialize_centroid(
    vec: np.ndarray,
    *,
    max_bytes: int,
) -> tuple[Dict[str, Any] | None, str | None]:
    """
    Encode an L2-normalized centroid as float32 JSON numbers.

    Returns (payload, error_reason). Payload includes dimension + values.
    """
    arr = np.asarray(vec, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        return None, "empty_centroid"
    if not np.all(np.isfinite(arr)):
        return None, "non_finite_centroid"
    norm = float(np.linalg.norm(arr))
    if norm <= 1e-12:
        return None, "zero_norm_centroid"
    arr = arr / norm
    norm2 = float(np.linalg.norm(arr))
    if abs(norm2 - 1.0) > NORM_TOLERANCE:
        return None, "norm_tolerance_exceeded"
    f32 = arr.astype(np.float32)
    values = [float(x) for x in f32.tolist()]
    payload = {"encoding": "float32_json", "dimension": int(f32.size), "values": values}
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    if len(encoded.encode("utf-8")) > int(max_bytes):
        return None, "centroid_bytes_exceeded"
    return payload, None


def deserialize_centroid(payload: Any) -> np.ndarray | None:
    if not isinstance(payload, dict):
        return None
    values = payload.get("values")
    dim = payload.get("dimension")
    if not isinstance(values, list) or not isinstance(dim, int):
        return None
    if len(values) != dim or dim <= 0:
        return None
    try:
        arr = np.asarray(values, dtype=np.float32).astype(np.float64)
    except (TypeError, ValueError):
        return None
    if arr.shape != (dim,) or not np.all(np.isfinite(arr)):
        return None
    return arr


def build_provenance(
    *,
    embedding_backend: str | None,
    model_name: str | None,
    model_revision: str | None,
    vector_dimension: int,
    fallback_vectorizer_signature: str | None,
) -> Dict[str, Any]:
    backend = str(embedding_backend or "unknown")
    model = str(model_name or "unknown")
    revision = str(model_revision or "unknown")
    major = parse_schema_major(SCHEMA_VERSION) or 1
    key_parts = [
        backend,
        model,
        revision,
        EMBEDDING_SEMANTICS_VERSION,
        f"major{major}",
        POOLING,
        f"trunc{TRUNCATION_LENGTH}",
        NORMALIZATION,
        f"dim{int(vector_dimension)}",
    ]
    if backend == "tfidf":
        key_parts.append(str(fallback_vectorizer_signature or "tfidf_unshared"))
    key = "|".join(key_parts)
    comparability = "incomparable" if backend == "tfidf" else "comparable"
    return {
        "provenance_compatibility_key": key,
        "embedding_backend": backend,
        "model_name": model,
        "model_revision": revision,
        "embedding_semantics_version": EMBEDDING_SEMANTICS_VERSION,
        "pooling": POOLING,
        "truncation_length": TRUNCATION_LENGTH,
        "normalization": NORMALIZATION,
        "vector_dimension": int(vector_dimension),
        "schema_major": int(major),
        "fallback_vectorizer_signature": fallback_vectorizer_signature,
        "comparability": comparability,
    }


def local_motif_id_from_refs(refs: Sequence[str]) -> str:
    joined = "|".join(sorted(refs))
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def build_motifs_from_clusters(
    rows: Sequence[SegmentRow],
    e_seg: np.ndarray,
    cluster_info: Dict[str, Any],
    *,
    motif_min_cluster_size: int,
    max_motifs_per_session: int,
    max_centroid_bytes: int,
    provenance: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], str, str | None]:
    """
    Build motif records from eligible-row labels.

    Returns (motifs, motif_export_status, reason).
    """
    n = len(rows)
    labels = cluster_info.get("labels") or []
    status = str(cluster_info.get("status") or "")
    if len(labels) != n or len(e_seg) != n:
        return [], "dependency_failure", "label_row_alignment_mismatch"
    if status == "dependency_missing":
        return [], "dependency_failure", str(cluster_info.get("reason") or status)
    if status == "clustering_failed":
        return [], "dependency_failure", str(cluster_info.get("reason") or status)

    by_label: Dict[int, List[int]] = {}
    for i, lab in enumerate(labels):
        lab_i = int(lab)
        if lab_i < 0:
            continue
        by_label.setdefault(lab_i, []).append(i)

    motifs: List[Dict[str, Any]] = []
    partial_reason: str | None = None
    min_size = max(1, int(motif_min_cluster_size))

    for lab in sorted(by_label.keys()):
        member_idxs = by_label[lab]
        if len(member_idxs) < min_size:
            continue
        member_vecs = e_seg[np.array(member_idxs, dtype=np.int64)]
        centroid = member_vecs.mean(axis=0)
        c_norm = float(np.linalg.norm(centroid))
        if c_norm <= 1e-12:
            continue
        centroid = centroid / c_norm
        # Nearest member to centroid; tie → lowest source_index then segment_id
        sims = member_vecs @ centroid
        best_local = None
        best_key = None
        for j, row_i in enumerate(member_idxs):
            row = rows[row_i]
            key = (-float(sims[j]), int(row.source_index), str(row.segment_id))
            if best_key is None or key < best_key:
                best_key = key
                best_local = j
        assert best_local is not None
        exemplar_row = rows[member_idxs[best_local]]
        refs = [stable_segment_ref(rows[i]) for i in member_idxs]
        refs_sorted = sorted(refs)
        ser, err = serialize_centroid(centroid, max_bytes=max_centroid_bytes)
        if ser is None:
            partial_reason = err or "centroid_serialize_failed"
            continue
        eligible_share = float(len(member_idxs)) / float(max(1, n))
        motifs.append(
            {
                "local_motif_id": local_motif_id_from_refs(refs_sorted),
                "cluster_label": int(lab),
                "size": int(len(member_idxs)),
                "eligible_segment_share": eligible_share,
                "centroid": ser,
                "exemplar_text": exemplar_row.text,
                "exemplar_segment_ref": stable_segment_ref(exemplar_row),
                "segment_refs": refs_sorted,
                "speakers": sorted({rows[i].display_name for i in member_idxs}),
            }
        )

    motifs.sort(
        key=lambda m: (
            -int(m.get("size") or 0),
            -float(m.get("eligible_segment_share") or 0.0),
            str(m.get("local_motif_id") or ""),
        )
    )
    cap = max(1, int(max_motifs_per_session))
    if len(motifs) > cap:
        motifs = motifs[:cap]
        partial_reason = partial_reason or "max_motifs_per_session"

    if provenance.get("comparability") == "incomparable":
        # Still export, but status notes incomparability at envelope level.
        pass

    if partial_reason and motifs:
        return motifs, "partial", partial_reason
    if partial_reason and not motifs:
        return [], "partial", partial_reason
    if not motifs:
        return [], "valid_zero", None
    return motifs, "ok", None


def empty_motif_envelope(
    *,
    status: str,
    reason: str | None,
    provenance: Dict[str, Any] | None,
    eligible_segment_count: int,
) -> Dict[str, Any]:
    prov = provenance or {}
    return {
        "motifs": [],
        "motif_export_status": status,
        "reason": reason,
        "provenance": prov,
        "eligible_segment_count": int(eligible_segment_count),
        "comparability": prov.get("comparability") or "incomparable",
    }


def attach_motif_envelope(
    results: Dict[str, Any],
    *,
    motifs: List[Dict[str, Any]],
    motif_export_status: str,
    reason: str | None,
    provenance: Dict[str, Any],
    eligible_segment_count: int,
) -> Dict[str, Any]:
    results["motifs"] = motifs
    results["motif_export_status"] = motif_export_status
    results["reason"] = reason if motif_export_status != "ok" else results.get("reason")
    if motif_export_status not in ("ok", "valid_zero") and reason:
        results["motif_export_reason"] = reason
    results["provenance"] = provenance
    results["eligible_segment_count"] = int(eligible_segment_count)
    results["comparability"] = provenance.get("comparability") or "incomparable"
    results["provenance_compatibility_key"] = provenance.get(
        "provenance_compatibility_key"
    )
    results["motif_count"] = len(motifs)
    return results
