"""Pipeline ImportError surfaces as blocked module result (no crash)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from transcriptx.core.analysis.semantic_similarity.analysis import (
    SemanticSimilarityV2Analysis,
)
from transcriptx.core.analysis.semantic_similarity.pipeline import (
    run_semantic_similarity_pipeline,
)
from transcriptx.core.analysis.semantic_similarity.config_resolve import (
    resolve_semantic_similarity_runtime,
)
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.analysis import SemanticSimilarityV2Config


def test_semantic_v2_import_error_returns_blocked() -> None:
    segments = [
        {
            "speaker": "A",
            "speaker_db_id": 1,
            "text": "hello world here",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "B",
            "speaker_db_id": 2,
            "text": "hello world there",
            "start": 1.0,
            "end": 2.0,
        },
    ]
    context = SimpleNamespace(
        transcript_path="/tmp/t.json",
        get_segments=lambda: segments,
        get_transcript_dir=lambda: "/tmp/out",
        get_run_id=lambda: "run-1",
        get_runtime_flags=lambda: {},
        store_analysis_result=lambda _n, _p: None,
        get_analysis_result=lambda _n: {"dummy": True},
    )
    with patch(
        "transcriptx.core.analysis.semantic_similarity.analysis.run_semantic_similarity_pipeline",
        side_effect=ImportError("torch"),
    ):
        mod = SemanticSimilarityV2Analysis()
        result = mod.run_from_context(context)
    assert result["status"] == "blocked"
    assert "missing_dependency" in result["metrics"].get("reason", "")


def test_semantic_v2_pipeline_records_missing_transformer_dependency() -> None:
    segments = [
        {
            "speaker": "A",
            "speaker_db_id": 1,
            "text": "hello world here",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "B",
            "speaker_db_id": 2,
            "text": "hello world there",
            "start": 1.0,
            "end": 2.0,
        },
    ]
    with patch(
        "transcriptx.core.analysis.semantic_similarity.pipeline.get_torch",
        side_effect=ImportError("torch"),
    ):
        results, diag = run_semantic_similarity_pipeline(
            segments,
            SemanticSimilarityV2Config(),
            resolve_diagnostics={},
        )

    assert diag.embedding_backend == "tfidf"
    assert diag.embedding_fallback_reason == "missing_transformer_dependency"
    assert diag.transformer_backend_available is False
    diag_payload = diag.to_dict()
    assert diag_payload["embedding_backend"] == "tfidf"
    assert diag_payload["embedding_fallback_reason"] == "missing_transformer_dependency"
    assert diag_payload["transformer_backend_available"] is False
    assert diag_payload["model_name"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert diag_payload["device"] is None
    assert diag_payload["batch_size"] == 64
    assert diag_payload["segments_deduplicated"] == 0
    assert diag_payload["effective_top_k"] == 50
    json.dumps(results)
    json.dumps(diag_payload)


def test_semantic_v2_advanced_mode_diagnostics_record_requested_and_effective() -> None:
    cfg = TranscriptXConfig()
    cfg.analysis.active_semantic_similarity_profile = "deep_v2"
    cfg.analysis.semantic_similarity.mode = "advanced"
    resolved, resolve_diag = resolve_semantic_similarity_runtime(
        cfg.analysis,
        modules_in_run={"sentiment"},
    )
    assert resolved.mode == "basic"
    assert resolve_diag["mode_requested"] == "advanced"
    assert resolve_diag["mode_effective"] == "basic"
    assert resolve_diag["advanced_integrations_unavailable"] == ["acts", "emotion"]

    segments = [
        {
            "speaker": "A",
            "speaker_db_id": 1,
            "text": "hello world here",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "B",
            "speaker_db_id": 2,
            "text": "hello world there",
            "start": 1.0,
            "end": 2.0,
        },
    ]
    with patch(
        "transcriptx.core.analysis.semantic_similarity.pipeline.get_torch",
        side_effect=ImportError("torch"),
    ):
        _results, diag = run_semantic_similarity_pipeline(
            segments,
            resolved,
            resolve_diagnostics=resolve_diag,
        )
    diag_payload = diag.to_dict()
    assert diag_payload["mode_requested"] == "advanced"
    assert diag_payload["mode_effective"] == "basic"
    assert diag_payload["advanced_integrations_unavailable"] == ["acts", "emotion"]


def test_semantic_v2_timeout_returns_structurally_valid_partial_results() -> None:
    """B14: timeout after embed still clusters for motif export (partial)."""
    segments = [
        {
            "speaker": "A",
            "speaker_db_id": 1,
            "text": "hello world here",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "B",
            "speaker_db_id": 2,
            "text": "hello world there",
            "start": 1.0,
            "end": 2.0,
        },
    ]
    cfg = SemanticSimilarityV2Config()
    cfg.timeout_seconds = 0.0
    with patch(
        "transcriptx.core.analysis.semantic_similarity.pipeline.get_torch",
        side_effect=ImportError("torch"),
    ):
        results, diag = run_semantic_similarity_pipeline(
            segments,
            cfg,
            resolve_diagnostics={},
        )

    assert diag.timeout_reached is True
    assert diag.partial_results is True
    assert results["speaker_repetitions"] == {}
    assert results["cross_speaker_repetitions"] == []
    assert results["segments"] == segments
    assert results.get("motif_export_status") in ("partial", "timeout", "valid_zero", "ok")
    assert "motifs" in results
    assert "schema_version" in results
    json.dumps(results)


def test_semantic_v2_runtime_error_returns_structured_error() -> None:
    segments = [
        {
            "speaker": "A",
            "speaker_db_id": 1,
            "text": "hello world here",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "speaker": "B",
            "speaker_db_id": 2,
            "text": "hello world there",
            "start": 1.0,
            "end": 2.0,
        },
    ]
    context = SimpleNamespace(
        transcript_path="/tmp/t.json",
        get_segments=lambda: segments,
        get_transcript_dir=lambda: "/tmp/out",
        get_run_id=lambda: "run-1",
        get_runtime_flags=lambda: {},
        store_analysis_result=lambda _n, _p: None,
        get_analysis_result=lambda _n: {"dummy": True},
    )
    with patch(
        "transcriptx.core.analysis.semantic_similarity.analysis.run_semantic_similarity_pipeline",
        side_effect=RuntimeError("bad model state"),
    ):
        mod = SemanticSimilarityV2Analysis()
        result = mod.run_from_context(context)
    assert result["status"] == "error"
    assert result["metrics"]["reason"] == "bad model state"
    assert result["metrics"]["exception_type"] == "RuntimeError"
