from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.sentiment import SentimentAnalysis  # type: ignore[import-untyped]


@pytest.mark.smoke
def test_sentiment_module_smoke_contract() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "tests" / "fixtures" / "mini_transcript.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    segments = payload["segments"]

    result = SentimentAnalysis().analyze(segments, speaker_map={})

    assert "segments_with_sentiment" in result
    assert result["segments_with_sentiment"], "expected at least one scored segment"
    first = result["segments_with_sentiment"][0]
    assert "sentiment" in first
    assert {"compound", "pos", "neu", "neg"}.issubset(set(first["sentiment"].keys()))

