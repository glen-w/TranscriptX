"""
Contract tests for artifact output conventions (offline + deterministic).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from transcriptx.core.analysis.sentiment import SentimentAnalysis
from transcriptx.core.utils import output_standards as output_standards_module
from transcriptx.core.utils.output_standards import (
    create_standard_output_structure,
    save_global_data,
    save_speaker_data,
)


def test_output_folder_contract(tmp_path, monkeypatch) -> None:
    outputs_root = tmp_path / "outputs"
    transcript_dir = outputs_root / "demo"
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        output_standards_module,
        "DIARISED_TRANSCRIPTS_DIR",
        str(tmp_path / "transcripts"),
    )

    structure = create_standard_output_structure(str(transcript_dir), "sentiment")
    saved = save_global_data({"ok": True}, structure, "demo", "sentiment", "json")

    assert saved.exists()
    assert structure.module_dir.exists()
    assert structure.data_dir.exists()
    assert structure.global_data_dir.exists()
    assert saved.name == "demo_sentiment.json"


def test_exclude_unknown_speaker_artifacts(tmp_path, monkeypatch) -> None:
    outputs_root = tmp_path / "outputs"
    transcript_dir = outputs_root / "demo"
    monkeypatch.setattr(output_standards_module, "OUTPUTS_DIR", str(outputs_root))
    monkeypatch.setattr(
        output_standards_module,
        "DIARISED_TRANSCRIPTS_DIR",
        str(tmp_path / "transcripts"),
    )

    structure = create_standard_output_structure(str(transcript_dir), "sentiment")
    result = save_speaker_data(
        {"ok": True}, structure, "demo", "SPEAKER_00", "sentiment", "json"
    )

    assert result is None
    assert not structure.speaker_data_dir.exists()


def test_sentiment_result_schema_contract() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "tests" / "fixtures" / "mini_transcript.json"
    segments = json.loads(fixture_path.read_text(encoding="utf-8"))["segments"]

    class _FakeSIA:
        def polarity_scores(self, _text):
            return {"compound": 0.1, "pos": 0.2, "neu": 0.7, "neg": 0.1}

    with patch(
        "transcriptx.core.analysis.sentiment._ensure_vader_lexicon", return_value=None
    ):
        with patch(
            "transcriptx.core.analysis.sentiment.SentimentIntensityAnalyzer",
            return_value=_FakeSIA(),
        ):
            result = SentimentAnalysis().analyze(segments, speaker_map={})

    assert "segments_with_sentiment" in result
    assert "global_stats" in result
    assert "speaker_stats" in result
    assert "summary" in result

    segments_with_sentiment = result["segments_with_sentiment"]
    assert isinstance(segments_with_sentiment, list)
    assert segments_with_sentiment
    first = segments_with_sentiment[0]
    assert "sentiment" in first
    assert {"compound", "pos", "neu", "neg"}.issubset(first["sentiment"].keys())
