"""Unit tests for UnderstandabilityAnalysis speaker grouping/inclusion.

These focus on *which speakers are included* (the behaviour that previously
dropped diarization-only transcripts), not on the readability math. The
readability metric computation (NLTK/textstat) is stubbed so the tests are
deterministic and do not require downloaded NLTK data.
"""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.understandability import UnderstandabilityAnalysis


@pytest.fixture
def _stub_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the readability metric computation with a deterministic stub."""

    def _fake_metrics(text: str) -> dict:
        return {"flesch_reading_ease": 50.0, "word_count": float(len(text.split()))}

    monkeypatch.setattr(
        "transcriptx.core.analysis.understandability.compute_understandability_metrics",
        _fake_metrics,
    )


def _segments(pairs: list[tuple[str, str]]) -> list[dict]:
    out = []
    start = 0.0
    for speaker, text in pairs:
        seg: dict = {"text": text, "start": start, "end": start + 1.0}
        if speaker is not None:
            seg["speaker"] = speaker
        out.append(seg)
        start += 1.0
    return out


@pytest.mark.unit
def test_named_speakers_are_included(_stub_metrics) -> None:
    segs = _segments([("Alice", "hello there friend"), ("Bob", "good to see you")])
    result = UnderstandabilityAnalysis().analyze(segs)
    assert set(result["scores"]) == {"Alice", "Bob"}
    assert result["skipped"] == 0
    assert result["global_stats"]  # non-empty


@pytest.mark.unit
def test_diarized_labels_are_included(_stub_metrics) -> None:
    """Regression: SPEAKER_xx labels must produce per-speaker scores."""
    segs = _segments(
        [
            ("SPEAKER_00", "the demo is next week"),
            ("SPEAKER_01", "yes the venue is downtown"),
            ("SPEAKER_00", "great please send the invite"),
        ]
    )
    result = UnderstandabilityAnalysis().analyze(segs)
    assert set(result["scores"]) == {"SPEAKER_00", "SPEAKER_01"}
    assert result["skipped"] == 0
    assert result["global_stats"]


@pytest.mark.unit
def test_mixed_named_and_diarized_speakers(_stub_metrics) -> None:
    segs = _segments(
        [("Alice", "hello there"), ("SPEAKER_01", "raw diarized turn here")]
    )
    result = UnderstandabilityAnalysis().analyze(segs)
    assert set(result["scores"]) == {"Alice", "SPEAKER_01"}
    assert result["skipped"] == 0


@pytest.mark.unit
def test_unknown_and_missing_labels_are_skipped(_stub_metrics) -> None:
    segs = _segments(
        [
            ("Unknown", "placeholder speaker text"),
            ("Unidentified Speaker", "another placeholder"),
            (None, "segment with no speaker field at all"),
            ("SPEAKER_00", "a real diarized turn"),
        ]
    )
    result = UnderstandabilityAnalysis().analyze(segs)
    # Only the diarized speaker is eligible; the rest are skipped.
    assert set(result["scores"]) == {"SPEAKER_00"}
    assert result["skipped"] == 3


@pytest.mark.unit
def test_empty_segments_yield_empty_result(_stub_metrics) -> None:
    result = UnderstandabilityAnalysis().analyze([])
    assert result["scores"] == {}
    assert result["global_stats"] == {}
    assert result["skipped"] == 0


@pytest.mark.unit
def test_save_results_passes_output_service_to_charts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: charts are only persisted when output_service is passed."""
    from unittest.mock import MagicMock

    captured: dict = {}

    def _fake_plot(scores, output_structure, base_name, output_service=None):
        captured["output_service"] = output_service

    monkeypatch.setattr(
        "transcriptx.core.analysis.understandability.plot_understandability_charts",
        _fake_plot,
    )
    monkeypatch.setattr(
        "transcriptx.core.utils.understandability.save_understandability_csv",
        lambda *a, **k: None,
    )

    output_service = MagicMock()
    output_service.base_name = "mini"
    output_service.get_output_structure.return_value = MagicMock()

    UnderstandabilityAnalysis()._save_results(
        {
            "scores": {"Alice": {"flesch_reading_ease": 70.0}},
            "speaker_stats": {"Alice": {"flesch_reading_ease": 70.0}},
            "global_stats": {"flesch_reading_ease": 70.0},
            "skipped": 0,
        },
        output_service,
    )

    assert captured["output_service"] is output_service
    output_service.save_data.assert_called_once()
    output_service.save_summary.assert_called_once()
