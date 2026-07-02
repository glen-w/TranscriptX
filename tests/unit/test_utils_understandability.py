"""Unit tests for transcriptx.core.utils.understandability helpers."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from transcriptx.core.utils import understandability as ua
from transcriptx.core.utils.output_standards import create_standard_output_structure


def _output_structure(tmp_path, monkeypatch: pytest.MonkeyPatch):
    outputs = tmp_path / "outputs"
    monkeypatch.setattr("transcriptx.core.utils.output_standards.OUTPUTS_DIR", outputs)
    transcript_dir = str(outputs / "mini")
    out = create_standard_output_structure(transcript_dir, "understandability")
    out.global_data_dir.mkdir(parents=True, exist_ok=True)
    out.speaker_data_dir.mkdir(parents=True, exist_ok=True)
    return out


@pytest.mark.unit
def test_compute_understandability_metrics_basic() -> None:
    text = "Hello world. This is a short sample sentence for testing."
    metrics = ua.compute_understandability_metrics(text)
    assert metrics["word_count"] > 0
    assert metrics["sentence_count"] >= 1
    assert "flesch_reading_ease" in metrics
    assert "lexical_density" in metrics
    assert 0.0 <= metrics["lexical_density"] <= 1.0


@pytest.mark.unit
def test_compute_understandability_metrics_empty_text() -> None:
    metrics = ua.compute_understandability_metrics("")
    assert metrics["word_count"] == 0
    assert metrics["sentence_count"] == 0
    assert metrics["avg_sentence_length"] == 0
    assert metrics["lexical_density"] == 0


@pytest.mark.unit
def test_save_understandability_csv_writes_named_speakers_only(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _output_structure(tmp_path, monkeypatch)
    scores = {
        "Alice": {"flesch_reading_ease": 70.0, "word_count": 12},
        "SPEAKER_00": {"flesch_reading_ease": 60.0, "word_count": 8},
        "Unknown": {"flesch_reading_ease": 50.0, "word_count": 4},
    }
    with patch.object(ua, "notify_user"):
        ua.save_understandability_csv(scores, out, "mini")

    global_csv = out.global_data_dir / "mini_understandability.csv"
    assert global_csv.exists()
    body = global_csv.read_text(encoding="utf-8")
    assert "Alice" in body
    assert "SPEAKER_00" not in body
    speaker_csv = out.speaker_data_dir / "mini_understandability_Alice.csv"
    assert speaker_csv.exists()


@pytest.mark.unit
def test_save_understandability_csv_skips_when_no_named_speakers(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _output_structure(tmp_path, monkeypatch)
    scores = {"SPEAKER_00": {"flesch_reading_ease": 60.0}}
    with patch.object(ua, "notify_user") as notify:
        ua.save_understandability_csv(scores, out, "mini")
    assert not (out.global_data_dir / "mini_understandability.csv").exists()
    notify.assert_called()


@pytest.mark.unit
def test_save_understandability_json_filters_named_speakers(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _output_structure(tmp_path, monkeypatch)
    scores = {
        "Bob": {"flesch_reading_ease": 55.0},
        "SPEAKER_01": {"flesch_reading_ease": 45.0},
    }
    with patch.object(ua, "notify_user"):
        ua.save_understandability_json(scores, out, "mini")

    global_json = out.global_data_dir / "mini_understandability.json"
    assert global_json.exists()
    payload = json.loads(global_json.read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"Bob"}
