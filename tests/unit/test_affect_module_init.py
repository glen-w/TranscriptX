"""Offline unit tests for lexical emotion v2 (filename avoids auto-marker)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from transcriptx.core.analysis.emotion import EmotionAnalysis, compute_nrc_emotions
from transcriptx.core.analysis.emotion.lexical_pipeline import (
    PLUTCHIK_EIGHT,
    build_lexicon_from_nrclex,
    score_segment_text,
)
from transcriptx.core.analysis.emotion.preflight import run_lexical_preflight
from transcriptx.core.analysis.emotion.projections import apply_lexical_projection
from transcriptx.core.analysis.emotion_family.persist import apply_pending_projections


@pytest.mark.unit
def test_preflight_ok_when_nrclex_present() -> None:
    pytest.importorskip("nrclex")
    result = run_lexical_preflight()
    assert result.ok is True


@pytest.mark.unit
def test_build_lexicon_nonempty() -> None:
    pytest.importorskip("nrclex")
    from nrclex import NRCLex

    lexicon = build_lexicon_from_nrclex(NRCLex)
    assert len(lexicon) > 100
    assert "abandon" in lexicon or "happy" in lexicon


@pytest.mark.unit
def test_score_segment_zero_denominator_safe() -> None:
    result = score_segment_text("", {})
    assert result.evaluation_state == "empty"
    assert result.coverage == 0.0
    assert all(v == 0.0 for v in result.emotion_scores.values())


@pytest.mark.unit
def test_analyze_sets_nrc_not_context() -> None:
    pytest.importorskip("nrclex")
    mod = EmotionAnalysis()
    segs = [
        {
            "id": "1",
            "speaker": "Alice",
            "text": "I feel happy and joyful",
            "start": 0,
            "end": 1,
        }
    ]
    out = mod.analyze(segs)
    assert out["usable_output"] is True
    assert "nrc_emotion" not in segs[0]
    assert out.get("_pending_projections")
    assert out.get("lexicon_digest")
    assert out.get("nrclex_version")
    apply_pending_projections(out, apply_one=apply_lexical_projection)
    assert "nrc_emotion" in segs[0]
    assert "context_emotion_source" not in segs[0]
    assert set(segs[0]["nrc_emotion"]) <= set(PLUTCHIK_EIGHT) | set(
        segs[0]["nrc_emotion"]
    )


@pytest.mark.unit
def test_compute_nrc_emotions_helper() -> None:
    pytest.importorskip("nrclex")
    scores = compute_nrc_emotions("happy joy love")
    assert isinstance(scores, dict)
    assert scores.get("joy", 0) > 0


@pytest.mark.unit
def test_save_results_writes_summary(tmp_path: Path) -> None:
    pytest.importorskip("nrclex")
    mod = EmotionAnalysis()
    segs = [
        {"id": "1", "speaker": "Alice", "text": "happy day", "start": 0, "end": 1},
        {"id": "2", "speaker": "Bob", "text": "sad news", "start": 1, "end": 2},
    ]
    results = mod.analyze(segs)
    assert "nrc_emotion" not in segs[0]
    output = MagicMock()
    output.base_name = "test"
    output.get_output_structure.return_value = MagicMock(module_dir=tmp_path)
    mod._save_results(results, output)
    assert "nrc_emotion" in segs[0]
    assert output.save_summary.called
    assert output.save_data.called
