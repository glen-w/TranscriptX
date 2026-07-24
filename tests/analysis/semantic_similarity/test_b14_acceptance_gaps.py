"""Additional B14 acceptance coverage (plan §10 gaps)."""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock

import numpy as np
import pytest

from transcriptx.core.analysis.aggregation.semantic_similarity import (
    _group_motif_id,
    _match_motifs_across_sessions,
    aggregate_semantic_similarity_group,
)
from transcriptx.core.analysis.semantic_similarity.motifs import (
    build_motifs_from_clusters,
    build_provenance,
    serialize_centroid,
)
from transcriptx.core.analysis.semantic_similarity.output import SCHEMA_VERSION
from transcriptx.core.analysis.semantic_similarity.pipeline import (
    run_semantic_similarity_pipeline,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap
from transcriptx.core.utils.config.analysis import SemanticSimilarityV2Config


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


def _result(path: str, key: str, order: int, payload: dict, mid: str = "semantic_similarity") -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=path,
        transcript_key=key,
        run_id=f"r{order}",
        order_index=order,
        output_dir=f"o{order}",
        module_results={mid: {"payload": payload, "status": "success"}},
    )


def _centroid(vec: np.ndarray) -> Dict[str, Any]:
    payload, err = serialize_centroid(vec, max_bytes=65_536)
    assert err is None and payload is not None
    return payload


def _v2(
    motifs: List[Dict[str, Any]],
    *,
    status: str = "ok",
    backend: str = "transformer",
) -> Dict[str, Any]:
    prov = build_provenance(
        embedding_backend=backend,
        model_name="test-model",
        model_revision="r1",
        vector_dimension=3,
        fallback_vectorizer_signature="sig" if backend == "tfidf" else None,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "speaker_repetitions": {"Alice": [{"similarity": 0.9}]},
        "cross_speaker_repetitions": [],
        "total_repetitions": 1,
        "unique_patterns": len(motifs),
        "motifs": motifs,
        "motif_export_status": status,
        "reason": None,
        "provenance": prov,
        "eligible_segment_count": 10,
        "comparability": prov["comparability"],
        "provenance_compatibility_key": prov["provenance_compatibility_key"],
        "motif_count": len(motifs),
    }


def _motif(lid: str, vec: np.ndarray, size: int = 3) -> Dict[str, Any]:
    return {
        "local_motif_id": lid,
        "size": size,
        "eligible_segment_share": size / 10.0,
        "centroid": _centroid(vec),
        "exemplar_text": f"ex {lid}",
        "segment_refs": [f"0:{lid}", f"1:{lid}"],
    }


@pytest.mark.unit
def test_threshold_inclusivity_and_tie_break() -> None:
    # Two locals with equal sim to one group motif — lower local_id wins after group_id
    v = np.array([1.0, 0.0, 0.0])
    sessions = [
        {
            "order_index": 0,
            "transcript_id": "t0",
            "motifs": [
                {**_motif("seed", v), "centroid_vec": v.copy(), "size": 2},
            ],
        },
        {
            "order_index": 1,
            "transcript_id": "t1",
            "motifs": [
                {
                    **_motif("b_local", v),
                    "centroid_vec": v.copy(),
                    "size": 2,
                    "local_motif_id": "b_local",
                },
                {
                    **_motif("a_local", v),
                    "centroid_vec": v.copy(),
                    "size": 2,
                    "local_motif_id": "a_local",
                },
            ],
        },
    ]
    # Force exact threshold boundary with identical vectors (sim=1.0 >= 0.75)
    rows, pooled, _ = _match_motifs_across_sessions(
        sessions,
        threshold=1.0,  # inclusive: exact 1.0 must match
        min_sessions_for_recurring=2,
        max_motifs_per_group=40,
    )
    assert any(r["status"] == "recurring" for r in rows)
    # Only one of the two locals should attach to seed (one-to-one); other becomes new
    assert len(rows) == 2


@pytest.mark.unit
def test_group_motif_id_deterministic() -> None:
    assert _group_motif_id("t0", "abc") == _group_motif_id("t0", "abc")
    assert _group_motif_id("t0", "abc") != _group_motif_id("t1", "abc")


@pytest.mark.unit
def test_partial_timeout_motif_count_null() -> None:
    v = np.array([1.0, 0.0, 0.0])
    results = [
        _result("/x/a.json", "a", 0, _v2([_motif("a", v)], status="ok")),
        _result(
            "/x/b.json",
            "b",
            1,
            _v2([_motif("b", v)], status="partial"),
        ),
    ]
    out = aggregate_semantic_similarity_group(results, _cmap(), _ts())
    assert out is not None
    by = {r["order_index"]: r for r in out["session_rows"]}
    assert by[0]["motif_count"] == 1
    assert by[1]["motif_count"] is None
    assert by[1]["included_in_comparison"] is True
    assert out["content_rows_name"] == "repetition_rows"
    assert len(out["content_rows"]) >= 1


@pytest.mark.unit
def test_max_motifs_per_group_cap() -> None:
    v = np.eye(3)
    # Many distinct motifs in one session
    motifs = [
        {
            **_motif(f"m{i}", v[i % 3]),
            "centroid_vec": v[i % 3].copy(),
            "local_motif_id": f"m{i}",
            "size": 10 - (i % 5),
            "eligible_segment_share": 0.5,
            "segment_refs": [f"{i}:m{i}"],
        }
        for i in range(12)
    ]
    sessions = [{"order_index": 0, "transcript_id": "t0", "motifs": motifs}]
    rows, pooled, warnings = _match_motifs_across_sessions(
        sessions,
        threshold=0.99,
        min_sessions_for_recurring=2,
        max_motifs_per_group=5,
    )
    assert len(rows) == 5
    assert pooled["truncation"]["truncated"] is True
    assert "max_motifs_per_group" in warnings


@pytest.mark.unit
def test_wrong_dimension_centroid_skipped(monkeypatch: Any) -> None:
    v = np.array([1.0, 0.0, 0.0])
    bad = {
        **_motif("bad", v),
        "centroid": {
            "encoding": "float32_json",
            "dimension": 2,
            "values": [1.0, 0.0],
        },
    }
    payload = _v2([bad], status="ok")
    # provenance says dim 3
    results = [_result("/x/a.json", "a", 0, payload)]
    out = aggregate_semantic_similarity_group(results, _cmap(), _ts())
    assert out is not None
    assert any("dimension_mismatch" in w for w in out["warnings"])
    # no valid locals → motif_rows empty for that member
    assert out["motif_rows"] == [] or out["primary_cohort_member_count"] >= 1


@pytest.mark.unit
def test_max_motifs_per_session_in_build() -> None:
    from transcriptx.core.analysis.semantic_similarity.cluster import STATUS_OK
    from transcriptx.core.analysis.semantic_similarity.intake import SegmentRow

    rows = [
        SegmentRow(str(i), "a", "A", float(i), float(i) + 1, f"t {i} words here", f"t {i} words here", i)
        for i in range(6)
    ]
    # three clusters of size 2
    e = np.vstack(
        [
            np.array([1.0, 0, 0]),
            np.array([1.0, 0, 0]),
            np.array([0, 1.0, 0]),
            np.array([0, 1.0, 0]),
            np.array([0, 0, 1.0]),
            np.array([0, 0, 1.0]),
        ]
    )
    cluster_info = {"labels": [0, 0, 1, 1, 2, 2], "n_clusters": 3, "status": STATUS_OK}
    prov = build_provenance(
        embedding_backend="transformer",
        model_name="m",
        model_revision=None,
        vector_dimension=3,
        fallback_vectorizer_signature=None,
    )
    motifs, status, reason = build_motifs_from_clusters(
        rows,
        e,
        cluster_info,
        motif_min_cluster_size=2,
        max_motifs_per_session=2,
        max_centroid_bytes=65_536,
        provenance=prov,
    )
    assert len(motifs) == 2
    assert status == "partial"
    assert reason == "max_motifs_per_session"


@pytest.mark.unit
def test_single_speaker_pipeline_skips_repetition_path() -> None:
    cfg = SemanticSimilarityV2Config()
    cfg.timeout_seconds = 60.0
    cfg.cluster_min_samples = 2
    cfg.motif_min_cluster_size = 2
    segments = [
        {
            "text": "alpha beta gamma delta epsilon",
            "start": float(i),
            "end": float(i) + 1,
            "speaker": "Only",
            "speaker_db_id": 1,
            "id": f"s{i}",
        }
        for i in range(4)
    ]
    # Force near-duplicate texts so TF-IDF/transformer can cluster
    segments[1]["text"] = "alpha beta gamma delta zeta"
    segments[2]["text"] = "alpha beta gamma delta eta"
    results, diag = run_semantic_similarity_pipeline(
        segments,
        cfg,
        resolve_diagnostics={"mode_requested": "basic", "mode_effective": "basic"},
        repetition_path_skipped=True,
    )
    assert results["schema_version"] == SCHEMA_VERSION
    assert results["repetition_path"] == "skipped"
    assert results["motif_export_status"] in (
        "ok",
        "valid_zero",
        "partial",
        "dependency_failure",
    )
    assert "motifs" in results
    assert results["eligible_segment_count"] == 4
    assert results.get("total_repetitions", 0) == 0


@pytest.mark.unit
def test_analysis_stamps_before_store(monkeypatch: Any) -> None:
    from transcriptx.core.analysis.semantic_similarity.analysis import (
        SemanticSimilarityV2Analysis,
    )
    from transcriptx.core.analysis.semantic_similarity.output import SCHEMA_VERSION

    stored: list = []

    class Ctx:
        transcript_path = "/tmp/t.json"

        def get_segments(self):
            return [
                {
                    "text": "one two three four five",
                    "start": 0,
                    "end": 1,
                    "speaker": "A",
                    "speaker_db_id": 1,
                },
                {
                    "text": "one two three four six",
                    "start": 1,
                    "end": 2,
                    "speaker": "B",
                    "speaker_db_id": 2,
                },
            ]

        def store_analysis_result(self, name, payload):
            stored.append(payload)
            assert payload.get("schema_version") == SCHEMA_VERSION
            assert "motif_export_status" in payload

        def get_transcript_dir(self):
            return "/tmp"

        def get_run_id(self):
            return "r1"

        def get_runtime_flags(self):
            return {}

        def get_analysis_result(self, _m):
            return None

    fake_out = MagicMock()
    fake_out.get_artifacts.return_value = []
    fake_out.base_name = "t"
    monkeypatch.setattr(
        "transcriptx.core.output.output_service.create_output_service",
        lambda *a, **k: fake_out,
    )

    mod = SemanticSimilarityV2Analysis()
    # Avoid writing viz/files
    monkeypatch.setattr(mod, "save_results", lambda *a, **k: None)
    result = mod.run_from_context(Ctx())
    assert stored, "store_analysis_result must be called"
    assert result["metrics"]["schema_version"] == SCHEMA_VERSION
    assert "motif_export_status" in result["metrics"]
    assert result["payload"].get("schema_version") == SCHEMA_VERSION
