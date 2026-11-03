"""Unit tests for speaker_map_diagnostics tier / partial status edges."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.speaker_map_diagnostics.analyze import (
    compute_speaker_map_diagnostics,
)


@pytest.mark.unit
def test_treat_as_single_speaker_is_t1() -> None:
    payload = compute_speaker_map_diagnostics(
        [{"speaker": "SPEAKER_00", "text": "solo"}],
        speaker_map={"SPEAKER_00": "SPEAKER_00"},
        treat_as_single_speaker=True,
    )
    assert payload["speaker_tier"] == "T1"
    assert payload["named_speaker_count"] == 0


@pytest.mark.unit
def test_allow_unnamed_speakers_is_t2() -> None:
    payload = compute_speaker_map_diagnostics(
        [{"speaker": "SPEAKER_00", "text": "hello"}],
        speaker_map={"SPEAKER_00": "SPEAKER_00"},
        allow_unnamed_speakers=True,
    )
    assert payload["speaker_tier"] == "T2"


@pytest.mark.unit
def test_missing_map_key_and_orphan_map_entry_are_partial() -> None:
    payload = compute_speaker_map_diagnostics(
        [
            {"speaker": "SPEAKER_00", "text": "a"},
            {"speaker": "SPEAKER_01", "text": "b"},
        ],
        speaker_map={"SPEAKER_00": "Alice", "SPEAKER_02": "Carol"},
    )
    assert payload["status"] == "partial"
    assert "SPEAKER_01" in payload["segment_labels_missing_from_map"]
    assert "SPEAKER_02" in payload["map_keys_missing_from_segments"]


@pytest.mark.unit
def test_duplicate_display_names_are_partial() -> None:
    payload = compute_speaker_map_diagnostics(
        [
            {"speaker": "SPEAKER_00", "text": "a"},
            {"speaker": "SPEAKER_01", "text": "b"},
        ],
        speaker_map={"SPEAKER_00": "Alice", "SPEAKER_01": "Alice"},
    )
    assert payload["status"] == "partial"
    assert "Alice" in payload["duplicate_display_names"]
    assert payload["speaker_tier"] == "T3"


@pytest.mark.unit
def test_voice_link_conflicts_are_partial() -> None:
    payload = compute_speaker_map_diagnostics(
        [
            {"speaker": "SPEAKER_00", "text": "a"},
            {"speaker": "SPEAKER_01", "text": "b"},
        ],
        speaker_map={"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"},
        speaker_id_to_db_id={"SPEAKER_00": "voice-1", "SPEAKER_01": "voice-1"},
    )
    assert payload["status"] == "partial"
    assert "voice-1" in payload["voice_link_conflicts"]
    assert payload["speaker_tier"] == "T3"
