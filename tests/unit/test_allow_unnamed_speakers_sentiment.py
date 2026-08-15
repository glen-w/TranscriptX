"""Sentiment retains diarized speaker buckets when unnamed speakers are allowed."""

from __future__ import annotations

import pytest

from transcriptx.utils.text_utils import (
    is_analysis_speaker_label,
    reset_pipeline_allow_unnamed_speakers,
    set_pipeline_allow_unnamed_speakers,
)


@pytest.mark.unit
def test_sentiment_named_filter_keeps_diarized_when_ungated() -> None:
    """Mirrors sentiment._is_named_speaker / speaker bucket filtering."""
    token = set_pipeline_allow_unnamed_speakers(True)
    try:
        speakers = ["SPEAKER_00", "SPEAKER_01", "Unknown", "Alice"]
        kept = [s for s in speakers if is_analysis_speaker_label(s)]
        assert kept == ["SPEAKER_00", "SPEAKER_01", "Alice"]
    finally:
        reset_pipeline_allow_unnamed_speakers(token)

    kept_default = [s for s in ["SPEAKER_00", "Alice"] if is_analysis_speaker_label(s)]
    assert kept_default == ["Alice"]
