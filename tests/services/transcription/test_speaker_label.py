"""Shared WhisperX speaker-label mapping for Granite and Nemotron converters."""

from __future__ import annotations

import pytest

from transcriptx.services.transcription.granite_json_to_whisperx import (
    speaker_label as granite_label,
)
from transcriptx.services.transcription.nemotron_json_to_whisperx import (
    speaker_label as nemotron_label,
)
from transcriptx.services.transcription.speaker_label import speaker_label


@pytest.mark.unit
def test_shared_speaker_label_one_based_matches_granite() -> None:
    assert speaker_label(1, one_based=True) == granite_label(1) == "SPEAKER_00"
    assert speaker_label("Speaker 2", one_based=True) == granite_label("Speaker 2")


@pytest.mark.unit
def test_shared_speaker_label_zero_based_matches_nemotron() -> None:
    assert speaker_label(0, one_based=False) == nemotron_label(0) == "SPEAKER_00"
    assert speaker_label("<spk:1>") == nemotron_label("<spk:1>") == "SPEAKER_01"
