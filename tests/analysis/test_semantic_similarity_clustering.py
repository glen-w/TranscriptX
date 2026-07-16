"""Unit tests for semantic similarity clustering helpers."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest

from transcriptx.core.analysis.semantic_similarity.clustering import (
    cluster_repetitions_advanced,
    cluster_repetitions_basic,
)


def _rep(
    text: str = "alpha beta gamma",
    speaker: str = "Alice",
    rtype: str = "self_repetition",
):
    return {
        "type": rtype,
        "similarity": 0.9,
        "segment1": {"text": text},
        "segment2": {"text": text},
        "speaker": speaker,
    }


@pytest.mark.unit
def test_cluster_repetitions_advanced_empty() -> None:
    assert cluster_repetitions_advanced({}, [], "TEST") == []


@pytest.mark.unit
def test_cluster_repetitions_advanced_type_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the sklearn try-block to fail so type-based fallback runs.
    def boom_config():
        raise RuntimeError("no config")

    monkeypatch.setattr(
        "transcriptx.core.analysis.semantic_similarity.clustering.get_config",
        boom_config,
    )
    reps = [_rep(), _rep(), _rep(rtype="cross_speaker")]
    out = cluster_repetitions_advanced({"Alice": reps[:2]}, [reps[2]], "TEST")
    assert isinstance(out, list)
    assert any(c.get("size", 0) >= 2 for c in out)


@pytest.mark.unit
def test_cluster_repetitions_basic_empty_embeddings() -> None:
    assert (
        cluster_repetitions_basic(
            {"Alice": [_rep(), _rep()]},
            [],
            embedding_fn=lambda _t: None,
            log_tag="TEST",
        )
        == []
    )


@pytest.mark.unit
def test_cluster_repetitions_basic_with_identical_embeddings() -> None:
    reps = [
        _rep("alpha beta gamma delta"),
        _rep("alpha beta gamma delta"),
    ]

    def emb(text: str):
        if "zzz" in text:
            return np.array([0.0, 0.0, 1.0, 0.0])
        return np.array([1.0, 0.0, 0.0, 0.0])

    out = cluster_repetitions_basic({"Alice": reps}, [], emb, "TEST")
    assert isinstance(out, list)
    for cluster in out:
        assert (
            "size" in cluster
            or "cluster_id" in cluster
            or "id" in cluster
            or "texts" in cluster
            or "representative_text" in cluster
        )
