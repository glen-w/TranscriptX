"""Tests for speaker map resolver helpers."""

from __future__ import annotations

from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    SpeakerMapState,
    is_effective_speaker_name,
    normalize_diarized_id,
    resolve_speaker_display_label,
)


def test_normalize_diarized_id_handles_numeric_and_speaker_prefix() -> None:
    assert normalize_diarized_id(1) == "SPEAKER_01"
    assert normalize_diarized_id("speaker_7") == "SPEAKER_07"
    assert normalize_diarized_id("  SPEAKER_07  ") == "SPEAKER_07"
    assert normalize_diarized_id(None) == ""


def test_is_effective_speaker_name_excludes_placeholder_self_map() -> None:
    assert is_effective_speaker_name("SPEAKER_00", "SPEAKER_00") is False
    assert is_effective_speaker_name("SPEAKER_00", "Alice") is True
    assert is_effective_speaker_name("SPEAKER_00", " ") is False


def test_resolve_speaker_display_label_prefers_identified_name() -> None:
    state = SpeakerMapState(
        has_sidecar=True,
        speaker_map={"SPEAKER_00": "Alice Smith", "SPEAKER_01": "SPEAKER_01"},
    )
    assert resolve_speaker_display_label("SPEAKER_00", state) == "Alice Smith"
    assert resolve_speaker_display_label("speaker_0", state) == "Alice Smith"
    assert resolve_speaker_display_label("SPEAKER_01", state) == "SPEAKER_01"
    assert resolve_speaker_display_label("SPEAKER_02", state) == "SPEAKER_02"
    assert resolve_speaker_display_label("", state) == ""
    assert resolve_speaker_display_label(None, None) == ""


def test_resolve_segments_applies_db_id_from_speaker_map_state() -> None:
    resolver = SpeakerMapResolver()
    state = SpeakerMapState(
        has_sidecar=True,
        speaker_map={"SPEAKER_00": "Alice"},
        speaker_id_to_db_id={"SPEAKER_00": 42},
    )
    segments = [{"speaker": "speaker_0", "text": "hello"}]
    out = resolver.resolve_segments(segments, state)
    assert out[0]["speaker"] == "Alice"
    assert out[0]["speaker_db_id"] == 42
