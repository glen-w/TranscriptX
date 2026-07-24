"""B14 motif export, clustering harden, epoch method fingerprint."""

from __future__ import annotations

import numpy as np
import pytest

from transcriptx.core.analysis.semantic_similarity.cluster import (
    STATUS_FAILED,
    STATUS_INSUFFICIENT,
    STATUS_OK,
    cluster_embeddings,
)
from transcriptx.core.analysis.semantic_similarity.intake import (
    SegmentRow,
    segment_rows_from_dicts,
)
from transcriptx.core.analysis.semantic_similarity.motifs import (
    build_motifs_from_clusters,
    build_provenance,
    deserialize_centroid,
    serialize_centroid,
)
from transcriptx.core.analysis.semantic_similarity.output import (
    SCHEMA_VERSION,
    parse_schema_major,
    reader_accepts_schema,
    with_schema,
)


def test_schema_constant_is_epoch_semantics() -> None:
    assert SCHEMA_VERSION == "transcriptx.semantic_similarity.semantics.1.1"
    assert parse_schema_major(SCHEMA_VERSION) == 1
    assert reader_accepts_schema(SCHEMA_VERSION)
    assert reader_accepts_schema("transcriptx.semantic_similarity.semantics.1")
    assert not reader_accepts_schema("transcriptx.semantic_similarity.semantics.2")
    assert parse_schema_major("transcriptx.semantic_similarity.semantics.2") == 2
    assert not reader_accepts_schema("semantic_similarity_v2.1.1")
    assert parse_schema_major("semantic_similarity_v2.1.1") is None


def test_with_schema_stamps_constant() -> None:
    assert with_schema({"a": 1})["schema_version"] == SCHEMA_VERSION


def test_cluster_insufficient_returns_aligned_noise() -> None:
    e = np.eye(1, dtype=np.float64)
    out = cluster_embeddings(e, min_samples=2)
    assert out["status"] == STATUS_INSUFFICIENT
    assert out["labels"] == [-1]
    assert out["n_clusters"] == 0


def test_cluster_failure_never_fabricates_single_cluster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    e = np.vstack([np.ones(4), np.ones(4) * 0.9, -np.ones(4)]).astype(np.float64)

    class Boom:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003
            raise RuntimeError("boom")

        def fit_predict(self, *_a, **_k):  # noqa: ANN002, ANN003
            raise RuntimeError("boom")

    import sklearn.cluster as skc

    monkeypatch.setattr(skc, "DBSCAN", Boom)
    out = cluster_embeddings(e, min_samples=2)
    assert out["status"] == STATUS_FAILED
    assert out["labels"] == [-1, -1, -1]
    assert out["n_clusters"] == 0


def test_cluster_ok_labels_length_matches_rows() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(size=(5, 8))
    a = a / np.linalg.norm(a, axis=1, keepdims=True)
    b = a[0] + rng.normal(scale=0.01, size=8)
    b = b / np.linalg.norm(b)
    e = np.vstack([a[:2], b.reshape(1, -1)])
    out = cluster_embeddings(e, min_samples=2, eps=0.5)
    assert len(out["labels"]) == 3
    assert out["status"] in (STATUS_OK, STATUS_FAILED, STATUS_INSUFFICIENT)


def _rows(n: int) -> list[SegmentRow]:
    return [
        SegmentRow(
            str(i),
            "a",
            "A",
            float(i),
            float(i) + 1,
            f"text {i} words here",
            f"text {i} words here",
            i,
        )
        for i in range(n)
    ]


def test_motif_build_uses_eligible_rows_source_index() -> None:
    rows, _ = segment_rows_from_dicts(
        [
            {"text": "skip", "start": 0, "end": 1, "speaker": "A"},  # too short
            {
                "text": "alpha beta gamma delta",
                "start": 1,
                "end": 2,
                "speaker": "A",
                "id": "s1",
            },
            {
                "text": "alpha beta gamma epsilon",
                "start": 2,
                "end": 3,
                "speaker": "A",
                "id": "s2",
            },
            {
                "text": "totally different topic words",
                "start": 3,
                "end": 4,
                "speaker": "B",
                "id": "s3",
            },
        ],
        min_words=3,
    )
    assert [r.source_index for r in rows] == [1, 2, 3]
    # Two near vectors + one far
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([0.99, 0.1, 0.0])
    v2 = v2 / np.linalg.norm(v2)
    v3 = np.array([0.0, 0.0, 1.0])
    e = np.vstack([v1, v2, v3])
    cluster_info = {"labels": [0, 0, -1], "n_clusters": 1, "status": STATUS_OK}
    prov = build_provenance(
        embedding_backend="transformer",
        model_name="test-model",
        model_revision="rev1",
        vector_dimension=3,
        fallback_vectorizer_signature=None,
    )
    motifs, status, reason = build_motifs_from_clusters(
        rows,
        e,
        cluster_info,
        motif_min_cluster_size=2,
        max_motifs_per_session=10,
        max_centroid_bytes=65_536,
        provenance=prov,
    )
    assert status == "ok"
    assert reason is None
    assert len(motifs) == 1
    assert motifs[0]["segment_refs"] == ["1:s1", "2:s2"]
    assert "0:" not in "".join(motifs[0]["segment_refs"])


def test_centroid_rejects_nan_and_wrong_bytes() -> None:
    bad = np.array([1.0, np.nan, 0.0])
    payload, err = serialize_centroid(bad, max_bytes=1000)
    assert payload is None
    assert err == "non_finite_centroid"

    good = np.array([1.0, 0.0, 0.0])
    payload, err = serialize_centroid(good, max_bytes=10)
    assert payload is None
    assert err == "centroid_bytes_exceeded"

    payload, err = serialize_centroid(good, max_bytes=10_000)
    assert err is None
    assert payload is not None
    assert payload["dimension"] == 3
    restored = deserialize_centroid(payload)
    assert restored is not None
    assert restored.shape == (3,)


def test_tfidf_provenance_is_incomparable() -> None:
    prov = build_provenance(
        embedding_backend="tfidf",
        model_name="n/a",
        model_revision=None,
        vector_dimension=128,
        fallback_vectorizer_signature="sig",
    )
    assert prov["comparability"] == "incomparable"
    assert "tfidf" in prov["provenance_compatibility_key"]


def test_valid_zero_motifs() -> None:
    rows = _rows(3)
    e = np.eye(3)
    cluster_info = {"labels": [-1, -1, -1], "n_clusters": 0, "status": STATUS_OK}
    prov = build_provenance(
        embedding_backend="transformer",
        model_name="m",
        model_revision=None,
        vector_dimension=3,
        fallback_vectorizer_signature=None,
    )
    motifs, status, _ = build_motifs_from_clusters(
        rows,
        e,
        cluster_info,
        motif_min_cluster_size=2,
        max_motifs_per_session=10,
        max_centroid_bytes=65_536,
        provenance=prov,
    )
    assert motifs == []
    assert status == "valid_zero"
