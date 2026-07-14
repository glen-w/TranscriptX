"""Tests for topic modeling utils helpers."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from transcriptx.core.analysis.topic_modeling import utils as tm_utils


def test_to_serializable_converts_numpy_scalars_and_arrays() -> None:
    payload = {
        "i": np.int64(3),
        "f": np.float64(1.5),
        "arr": np.array([1, 2]),
        "nested": [np.float32(2.5)],
    }
    out = tm_utils._to_serializable(payload)
    assert out["i"] == 3
    assert out["f"] == 1.5
    assert out["arr"] == [1, 2]
    assert out["nested"][0] == 2.5


def test_safe_numpy_array_handles_bad_values_and_ndarray() -> None:
    arr = tm_utils._safe_numpy_array(["1", "bad", 2], dtype=np.float64)
    assert arr.tolist() == [1.0, 0.0, 2.0]
    existing = np.array([3, 4], dtype=np.int32)
    converted = tm_utils._safe_numpy_array(existing, dtype=np.float64)
    assert converted.dtype == np.float64
    assert converted.tolist() == [3.0, 4.0]


def test_prepare_text_data_from_windows_handles_defaults() -> None:
    texts, speakers, starts = tm_utils.prepare_text_data_from_windows(
        {
            "windows": [
                {"text": "  ", "speakers": ["Alice"], "start": 10.0},
                {"text": "topic one", "speakers": ["Bob", "Alice", "Bob"], "start": 5},
                {"text": "topic two", "speakers": [], "start": None},
                "not_a_dict",
            ]
        }
    )
    assert texts == ["topic one", "topic two"]
    assert speakers == ["Alice / Bob", "window"]
    assert starts == [5.0, 0.0]


def test_prepare_text_data_from_windows_non_dict_input() -> None:
    assert tm_utils.prepare_text_data_from_windows(None) == ([], [], [])


@pytest.mark.heavy
@pytest.mark.slow
def test_get_segments_handles_dict_list_and_invalid_payloads(tmp_path: Path) -> None:
    as_dict = tmp_path / "dict.json"
    as_dict.write_text(json.dumps({"segments": [{"text": "a"}]}), encoding="utf-8")
    assert tm_utils._get_segments(str(as_dict)) == [{"text": "a"}]

    as_list = tmp_path / "list.json"
    as_list.write_text(json.dumps([{"text": "b"}]), encoding="utf-8")
    assert tm_utils._get_segments(str(as_list)) == [{"text": "b"}]

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{not-json", encoding="utf-8")
    assert tm_utils._get_segments(str(invalid)) == []


@pytest.mark.heavy
@pytest.mark.slow
def test_save_json_writes_serialized_numpy_payload(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "out.json"
    tm_utils._save_json({"x": np.array([1, 2]), "y": np.float64(2.5)}, str(target))
    assert target.is_file()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["x"] == [1, 2]
    assert data["y"] == 2.5


@pytest.mark.heavy
@pytest.mark.slow
def test_calculate_topic_coherence_returns_zero_on_vectorizer_errors() -> None:
    class _BadVectorizer:
        def transform(self, _texts):
            raise RuntimeError("boom")

    score = tm_utils.calculate_topic_coherence(
        top_words=["alpha", "beta"],
        texts=["alpha beta", "beta gamma"],
        vectorizer=_BadVectorizer(),
    )
    assert score == 0.0
