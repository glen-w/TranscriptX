"""Offline unit tests for BERTopic helpers, detection, and registry wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.aggregation.bertopic import (
    _validate_group_payload,
    inspect_member_bertopic_activation,
)
from transcriptx.core.analysis.bertopic.eligibility import evaluate_bertopic_eligibility
from transcriptx.core.analysis.bertopic.schema import validate_bertopic_artifact_payload
from transcriptx.core.analysis.bertopic.utils import (
    _coerce_float_list,
    build_doc_topic_data,
    build_topic_objects,
)
from transcriptx.core.analysis.group_charts.bertopic_group_charts import (
    BertopicGroupChartGenerator,
)
from transcriptx.core.pipeline.module_registry import (
    is_extra_distribution_present,
)
from transcriptx.core.pipeline.optional_dep_outcomes import (
    build_optional_dep_blocked_result,
    missing_extra_reason,
)
from transcriptx.core.pipeline.optional_extras import (
    is_extra_distribution_present as dist_present,
)
from transcriptx.core.utils.module_cache_config import get_cache_affecting_config


@pytest.mark.unit
def test_build_model_kwargs_applies_defaults_and_falsey_flags() -> None:
    from transcriptx.core.analysis.bertopic.runtime import build_model_kwargs

    cfg = SimpleNamespace(
        embedding_model="all-MiniLM-L6-v2",
        min_topic_size=5,
        nr_topics="auto",
        top_n_words=10,
        label_words=3,
        calculate_probabilities=False,
    )
    kwargs = build_model_kwargs(cfg)
    assert kwargs == {
        "embedding_model": "all-MiniLM-L6-v2",
        "min_topic_size": 5,
        "nr_topics": "auto",
        "top_n_words": 10,
        "calculate_probabilities": False,
    }
    assert "label_words" not in kwargs

    cfg.nr_topics = "12"
    cfg.calculate_probabilities = True
    kwargs = build_model_kwargs(cfg)
    assert kwargs["nr_topics"] == 12
    assert kwargs["calculate_probabilities"] is True


@pytest.mark.unit
def test_limited_native_threads_sets_and_restores_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import os

    from transcriptx.core.utils.native_threads import limited_native_threads

    monkeypatch.setenv("OMP_NUM_THREADS", "8")
    monkeypatch.delenv("MKL_NUM_THREADS", raising=False)
    with limited_native_threads(1):
        assert os.environ["OMP_NUM_THREADS"] == "1"
        assert os.environ["MKL_NUM_THREADS"] == "1"
    assert os.environ["OMP_NUM_THREADS"] == "8"
    assert "MKL_NUM_THREADS" not in os.environ


@pytest.mark.unit
def test_bertopic_settings_defaults_and_validation() -> None:
    from pydantic import ValidationError

    from transcriptx.core.config.models.bertopic import BERTopicSettingsModel

    defaults = BERTopicSettingsModel()
    assert defaults.embedding_model == "all-MiniLM-L6-v2"
    assert defaults.min_topic_size == 5
    assert defaults.nr_topics == "auto"
    assert defaults.top_n_words == 10
    assert defaults.label_words == 3
    assert defaults.calculate_probabilities is False
    assert defaults.timeout_seconds == 3600.0

    assert BERTopicSettingsModel(nr_topics="Auto").nr_topics == "auto"
    with pytest.raises(ValidationError):
        BERTopicSettingsModel(min_topic_size=1)
    with pytest.raises(ValidationError):
        BERTopicSettingsModel(nr_topics="none")
    with pytest.raises(ValidationError):
        BERTopicSettingsModel(embedding_model="  ")


@pytest.mark.unit
def test_coerce_float_list_none_and_bad_values() -> None:
    assert _coerce_float_list(None) is None
    assert _coerce_float_list([1, 2.5]) == [1.0, 2.5]
    assert _coerce_float_list(["x"]) is None


@pytest.mark.unit
def test_build_topic_objects_skips_outlier_and_adds_synthetic() -> None:
    model = MagicMock()
    model.get_topics.return_value = {
        -1: [("noise", 0.9)],
        0: [("alpha", 0.5), ("beta", 0.4), ("gamma", 0.1)],
        1: [],
    }
    info = MagicMock()
    info.iterrows.return_value = [
        (0, {"Topic": 0, "Count": 12}),
        (1, {"Topic": -1, "Count": 3}),
    ]
    model.get_topic_info.return_value = info

    topics = build_topic_objects(model, top_n_words=2, label_words=2)
    by_id = {t["topic_id"]: t for t in topics}
    assert 0 in by_id
    assert by_id[0]["words"] == ["alpha", "beta"]
    assert by_id[0]["label"] == "alpha, beta"
    assert by_id[0]["size"] == 12
    assert by_id[1]["words"] == []
    assert by_id[1]["weights"] is None
    assert by_id[-1]["label"] == "Outlier"
    assert by_id[-1]["label_source"] == "synthetic_outlier"
    assert -1 not in {
        t["topic_id"] for t in topics if t["label_source"] == "ctfidf_top_words"
    }


@pytest.mark.unit
def test_build_doc_topic_data_confidence_and_outlier_meta() -> None:
    docs, meta = build_doc_topic_data(
        topic_assignments=[-1, -1],
        topic_probs=[[0.1, 0.9], None],
        texts=["a", "b"],
        speaker_labels=["A", "B"],
        time_labels=[0.0, 1.0],
        doc_extra_fields=[{"segment_index": 0}, {"segment_index": 1}],
    )
    assert docs[0]["confidence"] == pytest.approx(0.9)
    assert docs[1]["confidence"] == 0.0
    assert docs[1]["topic_distribution"] is None
    assert meta["all_outlier"] is True
    assert meta["warning"] == "All documents classified as outliers"
    assert meta["doc_index_to_segment_index"] == {"0": 0, "1": 1}


@pytest.mark.unit
def test_build_doc_topic_data_skips_segment_map_for_group_fields() -> None:
    docs, meta = build_doc_topic_data(
        topic_assignments=[0],
        topic_probs=None,
        texts=["hello"],
        speaker_labels=["A"],
        time_labels=[0.0],
        doc_extra_fields=[{"transcript_id": "t1", "session_name": "s1"}],
    )
    assert docs[0]["transcript_id"] == "t1"
    assert docs[0]["confidence"] == 1.0
    assert "doc_index_to_segment_index" not in meta
    assert meta["all_outlier"] is False


@pytest.mark.unit
def test_validate_group_payload_reports_shape_issues() -> None:
    warnings = _validate_group_payload(
        [{"topic_id": 0, "words": ["a"], "weights": [0.1, 0.2]}],
        [{"doc_index": 0}],
    )
    assert any("weights length mismatch" in w for w in warnings)
    assert any("missing doc_index/dominant_topic" in w for w in warnings)

    warnings2 = _validate_group_payload("bad", "also-bad")
    assert any("topics payload is not a list" in w for w in warnings2)
    assert any("doc_topic_data payload is not a list" in w for w in warnings2)


@pytest.mark.unit
def test_validate_group_payload_accepts_minimal_valid() -> None:
    warnings = _validate_group_payload(
        [{"topic_id": 0, "words": ["alpha"], "weights": [1.0]}],
        [
            {
                "doc_index": 0,
                "dominant_topic": 0,
                "segment_index": 0,
                "transcript_id": "t1",
                "session_name": "s1",
            }
        ],
    )
    assert warnings == []


@pytest.mark.unit
def test_bertopic_analysis_module_imports_without_optional_package() -> None:
    """Retained module imports; package load is deferred via optional_import."""
    import importlib.util

    from transcriptx.core.analysis.bertopic import BERTopicAnalysis

    assert BERTopicAnalysis is not None
    _ = importlib.util.find_spec("bertopic")


@pytest.mark.unit
def test_eligibility_counts_duplicate_documents() -> None:
    docs = ["same", "same", "same"]
    decision = evaluate_bertopic_eligibility(docs)
    assert decision.eligible is True
    assert decision.documents_count == 3


@pytest.mark.unit
def test_eligibility_rejects_too_few() -> None:
    decision = evaluate_bertopic_eligibility(["a", "b"])
    assert decision.eligible is False
    assert decision.reason == "insufficient_documents"


@pytest.mark.unit
def test_artifact_schema_unsupported_version_skip() -> None:
    payload, warnings = validate_bertopic_artifact_payload(
        {"schema_version": 99, "topics": []}
    )
    assert payload is None
    assert any("unsupported" in w for w in warnings)


@pytest.mark.unit
def test_artifact_fixtures_load() -> None:
    from pathlib import Path
    import json

    root = Path(__file__).resolve().parents[2] / "fixtures" / "bertopic"
    current = json.loads((root / "artifact_current_v1.json").read_text())
    payload, warnings = validate_bertopic_artifact_payload(current)
    assert payload is not None and warnings == []

    pre = json.loads((root / "artifact_pre_rewire.json").read_text())
    payload2, warnings2 = validate_bertopic_artifact_payload(pre)
    assert payload2 is not None and warnings2 == []

    unsupported = json.loads((root / "artifact_unsupported_version.json").read_text())
    payload3, warnings3 = validate_bertopic_artifact_payload(unsupported)
    assert payload3 is None and any("unsupported" in w for w in warnings3)

    payload, warnings = validate_bertopic_artifact_payload(
        {"topics": [{"topic_id": 0, "words": ["a"]}]}
    )
    assert payload is not None
    assert warnings == []


@pytest.mark.unit
def test_artifact_schema_corrupt_rejected() -> None:
    payload, warnings = validate_bertopic_artifact_payload("not-a-dict")
    assert payload is None
    assert warnings


@pytest.mark.unit
def test_member_activation_skips_unsupported() -> None:
    ok, warnings = inspect_member_bertopic_activation({"schema_version": 42})
    assert ok is False
    assert any("unsupported" in w for w in warnings)


@pytest.mark.unit
def test_optional_dep_blocked_result_shape() -> None:
    result = build_optional_dep_blocked_result(
        module_name="bertopic",
        reason=missing_extra_reason("bertopic"),
        install_hint=(
            "pip install -e '.[bertopic]' "
            "(from a TranscriptX git checkout; not on PyPI)"
        ),
    )
    assert result["status"] == "blocked"
    assert result["metrics"]["reason"] == "missing_extra:bertopic"
    assert result["metrics"]["error_kind"] == "dependency"


@pytest.mark.unit
def test_distribution_present_probe_is_non_importing() -> None:
    # Catalogue helper must not require importing bertopic.
    present = dist_present("bertopic")
    assert present is is_extra_distribution_present("bertopic")
    assert isinstance(present, bool)


@pytest.mark.unit
def test_group_chart_no_spec_for_all_outlier() -> None:
    gen = BertopicGroupChartGenerator()
    assert (
        gen.can_generate(
            {
                "bertopic_pooled": {
                    "all_outlier": True,
                    "topics": [{"topic_id": 0, "topic_share": 1.0}],
                }
            }
        )
        is False
    )
    assert gen.can_generate({"bertopic_pooled": {"topics": []}}) is False
    assert (
        gen.can_generate(
            {
                "bertopic_pooled": {
                    "all_outlier": False,
                    "topics": [{"topic_id": 0, "topic_share": 0.5, "top_terms": "a"}],
                }
            }
        )
        is True
    )


@pytest.mark.unit
def test_cache_fingerprint_includes_fit_scope() -> None:
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            bertopic=SimpleNamespace(
                embedding_model="all-MiniLM-L6-v2",
                min_topic_size=5,
                nr_topics="auto",
                top_n_words=10,
                label_words=3,
                calculate_probabilities=False,
            )
        )
    )
    payload = get_cache_affecting_config("bertopic", cfg, fit_scope="group")
    assert payload["fit_scope"] == "group"
    assert payload["analysis.bertopic.embedding_model"] == "all-MiniLM-L6-v2"


@pytest.mark.unit
def test_bertopic_run_from_context_blocked_when_extra_missing() -> None:
    from transcriptx.core.analysis.bertopic import BERTopicAnalysis

    segments = [
        {"text": "alpha beta gamma delta", "speaker": "A", "start": 0.0, "end": 1.0},
        {"text": "epsilon zeta eta theta", "speaker": "B", "start": 1.0, "end": 2.0},
        {"text": "iota kappa lambda mu", "speaker": "A", "start": 2.0, "end": 3.0},
    ]
    context = SimpleNamespace(
        transcript_path="/tmp/t.json",
        get_segments=lambda: segments,
        get_transcript_dir=lambda: "/tmp/out",
        get_run_id=lambda: "run-1",
        get_runtime_flags=lambda: {},
        store_analysis_result=lambda _n, _p: None,
    )
    with (
        patch(
            "transcriptx.core.analysis.bertopic.analysis.verify_bertopic_import",
            return_value=(None, "missing_extra:bertopic"),
        ),
        patch(
            "transcriptx.core.analysis.bertopic.analysis.prepare_text_data",
            return_value=(
                ["alpha beta", "epsilon zeta", "iota kappa"],
                ["A", "B", "A"],
                [0.0, 1.0, 2.0],
                [0, 1, 2],
            ),
        ),
    ):
        result = BERTopicAnalysis().run_from_context(context)
    assert result["status"] == "blocked"
    assert result["metrics"]["reason"] == "missing_extra:bertopic"
