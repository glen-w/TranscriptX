from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.core.analysis.stats import StatsAnalysis  # type: ignore[import-untyped]
from transcriptx.utils.text_utils import is_named_speaker


@pytest.mark.smoke
def test_stats_module_smoke_excludes_unknown_speakers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = repo_root / "tests" / "fixtures" / "mini_transcript_with_unknown_speaker.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    segments = payload["segments"]

    result = StatsAnalysis().analyze(segments, speaker_map={})

    grouped = result["grouped_texts"]
    assert isinstance(grouped, dict)
    # Contract: only named speakers are included in grouped text aggregation.
    assert all(is_named_speaker(name) for name in grouped.keys())
    assert set(grouped.keys()) >= {"Alice", "Bob"}

