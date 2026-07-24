"""B14 group aggregation: cohort, matching, drift, null motif_count."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
import pytest

from transcriptx.core.analysis.aggregation.semantic_similarity import (
    aggregate_semantic_similarity_group,
)
from transcriptx.core.analysis.semantic_similarity.motifs import (
    build_provenance,
    serialize_centroid,
)
from transcriptx.core.analysis.semantic_similarity.output import SCHEMA_VERSION
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def _ts() -> TranscriptSet:
    return TranscriptSet.create(
        ["/x/a.json", "/x/b.json", "/x/c.json"], name="G", key="gk"
    )


def _cmap() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={
            "/x/a.json": {"1": 7},
            "/x/b.json": {"1": 7},
            "/x/c.json": {"1": 7},
        },
        canonical_to_display={7: "Alice"},
        transcript_to_display={
            "/x/a.json": {"1": "Alice"},
            "/x/b.json": {"1": "Alice"},
            "/x/c.json": {"1": "Alice"},
        },
    )


def _result(
    path: str,
    key: str,
    order: int,
    module_results: dict,
    output_dir: str = "o1",
) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=path,
        transcript_key=key,
        run_id=f"r{order}",
        order_index=order,
        output_dir=output_dir,
        module_results=module_results,
    )


def _centroid_payload(vec: np.ndarray) -> Dict[str, Any]:
    payload, err = serialize_centroid(vec, max_bytes=65_536)
    assert err is None and payload is not None
    return payload


def _v2_payload(
    *,
    motifs: List[Dict[str, Any]],
    status: str = "ok",
    backend: str = "transformer",
    dim: int = 3,
    model: str = "test-model",
) -> Dict[str, Any]:
    prov = build_provenance(
        embedding_backend=backend,
        model_name=model,
        model_revision="r1",
        vector_dimension=dim,
        fallback_vectorizer_signature="sig" if backend == "tfidf" else None,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "speaker_repetitions": {},
        "cross_speaker_repetitions": [],
        "total_repetitions": 0,
        "unique_patterns": len(motifs),
        "motifs": motifs,
        "motif_export_status": status,
        "reason": None if status in ("ok", "valid_zero") else status,
        "provenance": prov,
        "eligible_segment_count": 10,
        "comparability": prov["comparability"],
        "provenance_compatibility_key": prov["provenance_compatibility_key"],
        "motif_count": len(motifs),
    }


def _motif(local_id: str, vec: np.ndarray, size: int = 3) -> Dict[str, Any]:
    return {
        "local_motif_id": local_id,
        "size": size,
        "eligible_segment_share": size / 10.0,
        "centroid": _centroid_payload(vec),
        "exemplar_text": f"exemplar {local_id}",
        "segment_refs": [f"0:{local_id}", f"1:{local_id}"],
    }


@pytest.mark.unit
def test_matching_one_to_one_and_recurring() -> None:
    v = np.array([1.0, 0.0, 0.0])
    v2 = np.array([0.99, 0.05, 0.0])
    v2 = v2 / np.linalg.norm(v2)
    other = np.array([0.0, 1.0, 0.0])

    results = [
        _result(
            "/x/a.json",
            "a",
            0,
            {
                "semantic_similarity": {
                    "payload": _v2_payload(motifs=[_motif("a", v), _motif("b", other)])
                }
            },
        ),
        _result(
            "/x/b.json",
            "b",
            1,
            {"semantic_similarity": {"payload": _v2_payload(motifs=[_motif("c", v2)])}},
            output_dir="o2",
        ),
        _result(
            "/x/c.json",
            "c",
            2,
            {
                "semantic_similarity": {
                    "payload": _v2_payload(motifs=[], status="valid_zero")
                }
            },
            output_dir="o3",
        ),
    ]
    out = aggregate_semantic_similarity_group(results, _cmap(), _ts())
    assert out is not None
    assert out["content_rows_name"] == "repetition_rows"
    assert "motif_rows" in out
    assert out.get("extra_tables", {}).get("motif_rows") == out["motif_rows"]
    assert "semantic_similarity_pooled" in out
    assert out["primary_cohort_member_count"] == 3
    recurring = [m for m in out["motif_rows"] if m["status"] == "recurring"]
    assert len(recurring) >= 1
    by_order = {r["order_index"]: r for r in out["session_rows"]}
    assert by_order[0]["drift_score"] is None
    assert isinstance(by_order[1]["drift_score"], float)
    assert by_order[2]["motif_count"] == 0


@pytest.mark.unit
def test_tfidf_excluded_from_cohort() -> None:
    v = np.array([1.0, 0.0, 0.0])
    results = [
        _result(
            "/x/a.json",
            "a",
            0,
            {"semantic_similarity": {"payload": _v2_payload(motifs=[_motif("a", v)])}},
        ),
        _result(
            "/x/b.json",
            "b",
            1,
            {
                "semantic_similarity": {
                    "payload": _v2_payload(motifs=[_motif("b", v)], backend="tfidf")
                }
            },
            output_dir="o2",
        ),
    ]
    out = aggregate_semantic_similarity_group(results, _cmap(), _ts())
    assert out is not None
    assert out["primary_cohort_member_count"] == 1
    reasons = {e["reason"] for e in out["excluded_members"]}
    assert "incomparable_backend" in reasons
    bad_row = next(r for r in out["session_rows"] if r.get("order_index") == 1)
    assert bad_row["motif_count"] is None
    assert bad_row["included_in_comparison"] is False


@pytest.mark.unit
def test_legacy_payload_null_motif_count() -> None:
    legacy = {
        "total_repetitions": 2,
        "unique_patterns": 1,
        "speaker_repetitions": {},
        "cross_speaker_repetitions": [],
    }
    results = [
        _result(
            "/x/a.json",
            "a",
            0,
            {"semantic_similarity": {"payload": legacy}},
        )
    ]
    out = aggregate_semantic_similarity_group(results, _cmap(), _ts())
    assert out is not None
    assert out["session_rows"][0]["motif_count"] is None
    assert out["motif_rows"] == []


@pytest.mark.unit
def test_chart_generator_requires_recurring() -> None:
    from transcriptx.core.analysis.group_charts.semantic_similarity_charts import (
        SemanticSimilarityGroupChartGenerator,
    )

    gen = SemanticSimilarityGroupChartGenerator()
    outcome = {
        "session_rows": [
            {"order_index": 0, "included_in_comparison": True, "total_repetitions": 1},
            {"order_index": 1, "included_in_comparison": True, "total_repetitions": 2},
        ],
        "semantic_similarity_pooled": {
            "order_indexes": [0, 1],
            "recurring_motif_ids": [],
            "motif_ids": [],
            "strength_matrix": [],
        },
    }
    assert gen._can_motif_prevalence(outcome) is False
    outcome["semantic_similarity_pooled"]["recurring_motif_ids"] = ["abc"]
    outcome["semantic_similarity_pooled"]["motif_ids"] = ["abc"]
    outcome["semantic_similarity_pooled"]["strength_matrix"] = [[1.0, 2.0]]
    assert gen._can_motif_prevalence(outcome) is True


@pytest.mark.unit
def test_registry_single_semantic_generator() -> None:
    from transcriptx.core.analysis.group_charts.registry import build_group_chart_registry
    from transcriptx.core.analysis.group_charts.semantic_similarity_charts import (
        SemanticSimilarityGroupChartGenerator,
    )

    reg = build_group_chart_registry()
    assert isinstance(reg["semantic_similarity"], SemanticSimilarityGroupChartGenerator)
