"""Unit tests for file_rename audio candidate path helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.utils.file_rename import (
    _audio_lookup_bases,
    _fallback_audio_candidate_paths_no_state,
    _looks_like_uuid,
    ordered_audio_candidate_paths_for_state_entry,
)


@pytest.mark.unit
def test_looks_like_uuid() -> None:
    assert _looks_like_uuid("550e8400-e29b-41d4-a716-446655440000") is True
    assert _looks_like_uuid("/path/to/file.wav") is False
    assert _looks_like_uuid("short") is False


@pytest.mark.unit
def test_audio_lookup_bases_dedupes_and_skips_empty() -> None:
    bases = _audio_lookup_bases("base", "", "base", "other")
    assert bases == ["base", "other"]


@pytest.mark.unit
def test_ordered_audio_candidate_paths_prefers_metadata_paths(tmp_path: Path) -> None:
    recordings = (tmp_path / "rec",)
    recordings[0].mkdir()
    metadata = {
        "audio_path": str(tmp_path / "a.wav"),
        "mp3_path": str(tmp_path / "a.mp3"),
        "convert": {"mp3_path": str(tmp_path / "convert.mp3")},
        "steps": {"convert": {"mp3_path": str(tmp_path / "legacy.mp3")}},
    }
    candidates = ordered_audio_candidate_paths_for_state_entry(
        file_key=str(tmp_path / "key.wav"),
        metadata=metadata,
        transcript_path=str(tmp_path / "t.json"),
        resolved_audio_from_transcript=str(tmp_path / "resolved.wav"),
        transcript_base="t",
        canonical_base_from_metadata="canonical",
        base_without_suffix="base",
        recordings_dirs=recordings,
        audio_extensions=(".wav", ".mp3"),
    )
    assert candidates[0] == str(tmp_path / "a.wav")
    assert str(tmp_path / "a.mp3") in candidates
    assert str(tmp_path / "resolved.wav") in candidates


@pytest.mark.unit
def test_fallback_audio_candidate_paths_no_state(tmp_path: Path) -> None:
    recordings = (tmp_path / "rec",)
    recordings[0].mkdir()
    candidates = _fallback_audio_candidate_paths_no_state(
        str(tmp_path / "t.json"),
        resolved_full=str(tmp_path / "full.wav"),
        resolved_stripped=str(tmp_path / "strip.wav"),
        transcript_base="t",
        base_without_suffix="t",
        recordings_dirs=recordings,
        audio_extensions=(".wav",),
    )
    assert candidates[0] == str(tmp_path / "full.wav")
    assert str(tmp_path / "strip.wav") in candidates
