"""Unit tests for transcriptx.core.utils.understandability helpers."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

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


@pytest.mark.unit
def test_plot_understandability_charts_skips_without_named_speakers(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _output_structure(tmp_path, monkeypatch)
    with patch.object(ua, "notify_user") as notify:
        ua.plot_understandability_charts(
            {"SPEAKER_00": {"flesch_reading_ease": 60.0}},
            out,
            "mini",
            output_service=MagicMock(),
        )
    notify.assert_called()


@pytest.mark.unit
def test_plot_understandability_charts_skips_missing_columns(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _output_structure(tmp_path, monkeypatch)
    with patch.object(ua, "notify_user") as notify:
        ua.plot_understandability_charts(
            {"Alice": {"flesch_reading_ease": 70.0, "word_count": 10}},
            out,
            "mini",
            output_service=MagicMock(),
        )
    notify.assert_called()


@pytest.mark.unit
def test_plot_understandability_charts_requires_output_service(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _output_structure(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="output_service is required"):
        ua.plot_understandability_charts(
            {"Alice": {"flesch_reading_ease": 70.0}}, out, "mini", output_service=None
        )


@pytest.mark.unit
def test_plot_understandability_charts_success_path(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _output_structure(tmp_path, monkeypatch)
    scores = {
        "Alice": {
            "flesch_reading_ease": 70.0,
            "gunning_fog_index": 8.0,
            "smog_index": 7.0,
            "automated_readability_index": 6.0,
            "lexical_density": 0.5,
            "avg_sentence_length": 12.0,
            "sentence_count": 3,
            "word_count": 40,
        },
        "Bob": {
            "flesch_reading_ease": 55.0,
            "gunning_fog_index": 10.0,
            "smog_index": 9.0,
            "automated_readability_index": 8.0,
            "lexical_density": 0.4,
            "avg_sentence_length": 15.0,
            "sentence_count": 4,
            "word_count": 60,
        },
    }
    output_service = MagicMock()
    with (
        patch.object(ua, "notify_user"),
        patch.object(ua.plt, "figure"),
        patch.object(ua.plt, "title"),
        patch.object(ua.plt, "xticks"),
        patch.object(ua.plt, "tight_layout"),
        patch.object(ua.plt, "close"),
        patch.object(ua.plt, "gcf", return_value=MagicMock()),
        patch.object(
            ua.sns, "barplot", return_value=MagicMock(get_xticklabels=lambda: [])
        ),
        patch.object(ua.sns, "color_palette", return_value=MagicMock()),
    ):
        ua.plot_understandability_charts(
            scores, out, "mini", output_service=output_service
        )
    assert output_service.save_chart.call_count >= 1


@pytest.mark.unit
def test_ensure_nltk_helpers_download_and_error() -> None:
    with (
        patch("nltk.data.find", side_effect=LookupError("missing")),
        patch("nltk.download") as download,
        patch.object(ua, "notify_user"),
    ):
        ua._ensure_nltk_punkt()
        ua._ensure_nltk_cmudict()
    assert download.call_count >= 2

    with (
        patch("nltk.data.find", side_effect=RuntimeError("broken")),
        patch.object(ua, "notify_user", side_effect=RuntimeError("notify broken")),
        pytest.raises(RuntimeError),
    ):
        ua._ensure_nltk_punkt()


@pytest.mark.unit
def test_compute_and_save_understandability_named_only(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = tmp_path / "outputs"
    out_dir = outputs / "run"
    out_dir.mkdir(parents=True)
    segments = [
        {"speaker": "Alice", "text": "Hello world. This is a readable sentence."},
        {"speaker": "SPEAKER_00", "text": "ignored diarization label content here."},
    ]
    monkeypatch.setattr("transcriptx.core.utils.output_standards.OUTPUTS_DIR", outputs)
    with (
        patch.object(ua, "notify_user"),
        patch.object(ua, "create_output_service", return_value=None),
        patch.object(ua, "save_understandability_json") as save_json,
        patch.object(ua, "save_understandability_csv"),
        patch.object(ua, "plot_understandability_charts"),
    ):
        result = ua.compute_and_save_understandability(segments, str(out_dir), "mini")
    assert isinstance(result, dict)
    assert "Alice" in result
    assert "SPEAKER_00" not in result
    save_json.assert_called_once()
