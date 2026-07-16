"""Offline unit tests for BERTopic output-shaping helpers (no bertopic install).

BERTopic remains unwired from the module/aggregation registries due to dependency
conflicts; these tests cover retained pure helpers only.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.aggregation.bertopic import _validate_group_payload
from transcriptx.core.analysis.bertopic.utils import (
    _coerce_float_list,
    build_doc_topic_data,
    build_topic_objects,
)
from transcriptx.core.pipeline.module_registry import get_available_modules
from transcriptx.core.pipeline.module_registry_specs import MODULE_CLASS_MAP


@pytest.mark.unit
def test_bertopic_not_registered_in_module_class_map() -> None:
    assert "bertopic" not in MODULE_CLASS_MAP
    assert "bertopic" not in get_available_modules()


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
    assert "warning" not in meta


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
    # Current default env keeps bertopic unwired/uninstalled; tolerate either.
    _ = importlib.util.find_spec("bertopic")
