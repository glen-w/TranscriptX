"""Tests for suggest_rename_base_name shared helper."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptx.core.utils.rename.date_prefix import (
    extract_date_prefix_from_filename,
    suggest_rename_base_name,
)


@pytest.mark.unit
def test_suggest_prefills_date_prefix_plus_stem(tmp_path: Path) -> None:
    audio = tmp_path / "251230_recording.wav"
    audio.write_bytes(b"x")
    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}", encoding="utf-8")
    assert (
        suggest_rename_base_name(
            transcript,
            prefill_with_date_prefix=True,
            audio_path=audio,
            smart_rename_mode="off",
        )
        == "251230_meeting"
    )


@pytest.mark.unit
def test_suggest_no_double_prefix_when_stem_already_dated(tmp_path: Path) -> None:
    transcript = tmp_path / "251230_meeting.json"
    transcript.write_text("{}", encoding="utf-8")
    assert (
        suggest_rename_base_name(
            transcript, prefill_with_date_prefix=True, smart_rename_mode="off"
        )
        == "251230_meeting"
    )


@pytest.mark.unit
def test_suggest_respects_prefill_disabled(tmp_path: Path) -> None:
    transcript = tmp_path / "251230_meeting.json"
    transcript.write_text("{}", encoding="utf-8")
    assert (
        suggest_rename_base_name(
            transcript, prefill_with_date_prefix=False, smart_rename_mode="off"
        )
        == "251230_meeting"
    )


@pytest.mark.unit
def test_suggest_falls_back_to_mtime_when_no_filename_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transcript = tmp_path / "plain.json"
    transcript.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.date_prefix.find_original_audio_file",
        lambda _p: None,
        raising=False,
    )
    # Patch audio association import path used inside resolve_rename_date_prefix.
    monkeypatch.setattr(
        "transcriptx.core.utils.rename.audio_association.find_original_audio_file",
        lambda _p: None,
    )
    suggested = suggest_rename_base_name(
        transcript, prefill_with_date_prefix=True, smart_rename_mode="off"
    )
    assert suggested.endswith("_plain")
    prefix = suggested[:7]
    assert len(prefix) == 7 and prefix.endswith("_")
    assert prefix[:6].isdigit()


@pytest.mark.unit
def test_filename_extraction_contract() -> None:
    assert extract_date_prefix_from_filename("20251230160235.wav") == "251230_"
    assert extract_date_prefix_from_filename("251230_meeting.wav") == "251230_"
    assert extract_date_prefix_from_filename("R20260810-173237.wav") == "260810_"
    assert extract_date_prefix_from_filename("260725-164140.wav") == "260725_"


@pytest.mark.unit
def test_suggest_smart_mode_uses_pattern(tmp_path: Path) -> None:
    transcript = tmp_path / "R20260810-173237.json"
    transcript.write_text("{}", encoding="utf-8")
    suggested = suggest_rename_base_name(
        transcript,
        smart_rename_mode="suggest_import",
        smart_rename_pattern="{yymmdd}_{period}_{n}",
    )
    assert suggested == "260810_evening_1"
