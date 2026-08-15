"""Unit tests for deterministic smart rename from device filenames."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from transcriptx.core.utils.rename.smart_name import (
    append_token_to_name,
    build_rename_tokens,
    next_sequence_number,
    parse_recording_datetime_from_stem,
    parse_voice_note_stem,
    period_for_hour,
    render_smart_rename,
    resolve_smart_rename_pattern,
    smart_rename_applies_on_import,
    smart_rename_auto_on_import,
    smart_rename_suggests_in_rename_workflow,
    suggest_smart_rename_base_name,
    validate_smart_rename_pattern,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("stem", "expected"),
    [
        ("R20260810-173237", datetime(2026, 8, 10, 17, 32, 37)),
        ("20260620235550", datetime(2026, 6, 20, 23, 55, 50)),
        ("260725-164140", datetime(2026, 7, 25, 16, 41, 40)),
        ("20251230160235", datetime(2025, 12, 30, 16, 2, 35)),
        ("251230_meeting", datetime(2025, 12, 30, 0, 0, 0)),
    ],
)
def test_parse_device_stems(stem: str, expected: datetime) -> None:
    assert parse_recording_datetime_from_stem(stem) == expected


@pytest.mark.unit
def test_parse_rejects_garbage() -> None:
    assert parse_recording_datetime_from_stem("plain_name") is None
    assert parse_recording_datetime_from_stem("R20261340-999999") is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("hour", "period"),
    [
        (5, "morning"),
        (11, "morning"),
        (12, "afternoon"),
        (16, "afternoon"),
        (17, "evening"),
        (20, "evening"),
        (21, "night"),
        (4, "night"),
        (0, "night"),
    ],
)
def test_period_buckets(hour: int, period: str) -> None:
    assert period_for_hour(hour) == period


@pytest.mark.unit
def test_render_default_pattern_and_collision() -> None:
    tokens = build_rename_tokens(datetime(2026, 8, 10, 17, 32, 37), stem="x")
    assert (
        render_smart_rename("{yymmdd}_{period}_{n}", tokens, existing_stems=[])
        == "260810_evening_1"
    )
    assert (
        render_smart_rename(
            "{yymmdd}_{period}_{n}",
            tokens,
            existing_stems=["260810_evening_1", "260810_evening_2"],
        )
        == "260810_evening_3"
    )


@pytest.mark.unit
def test_configurable_date_pattern() -> None:
    tokens = build_rename_tokens(datetime(2026, 8, 10, 9, 0, 0), stem="x")
    assert (
        render_smart_rename("{yyyymmdd}_{hhmm}", tokens, existing_stems=[])
        == "20260810_0900"
    )


@pytest.mark.unit
def test_invalid_pattern_falls_back_to_default() -> None:
    ok, _ = validate_smart_rename_pattern("{yymmdd}_{bogus}")
    assert not ok
    assert resolve_smart_rename_pattern("{yymmdd}_{bogus}") == "{yymmdd}_{period}_{n}"


@pytest.mark.unit
def test_next_sequence_number() -> None:
    assert next_sequence_number("260810_afternoon_", ["260810_afternoon_1"]) == 2
    assert next_sequence_number("260810_afternoon_", []) == 1


@pytest.mark.unit
def test_append_token_to_name() -> None:
    assert append_token_to_name("260810_", "afternoon") == "260810_afternoon"
    assert append_token_to_name("260810_afternoon", "1") == "260810_afternoon_1"
    assert append_token_to_name("", "afternoon") == "afternoon"


@pytest.mark.unit
def test_mode_helpers() -> None:
    assert smart_rename_applies_on_import("suggest_import")
    assert smart_rename_applies_on_import("auto_import")
    assert not smart_rename_applies_on_import("suggest_rename_only")
    assert smart_rename_auto_on_import("auto_import")
    assert not smart_rename_auto_on_import("suggest_import")
    assert smart_rename_suggests_in_rename_workflow("suggest_rename_only")
    assert not smart_rename_suggests_in_rename_workflow("off")


@pytest.mark.unit
def test_suggest_smart_rename_base_name(tmp_path: Path) -> None:
    path = tmp_path / "R20260810-173237.json"
    path.write_text("{}", encoding="utf-8")
    suggestion = suggest_smart_rename_base_name(
        path,
        mode="suggest_import",
        pattern="{yymmdd}_{period}_{n}",
        transcripts_dir=tmp_path,
    )
    assert suggestion is not None
    assert suggestion.full == "260810_evening_1"
    assert suggestion.date_root == "260810_"
    assert "evening" in suggestion.token_bubbles
    assert "1" in suggestion.token_bubbles


@pytest.mark.unit
def test_suggest_off_returns_none(tmp_path: Path) -> None:
    path = tmp_path / "R20260810-173237.json"
    path.write_text("{}", encoding="utf-8")
    assert (
        suggest_smart_rename_base_name(path, mode="off", transcripts_dir=tmp_path)
        is None
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("stem", "family", "has_dt", "sequence"),
    [
        ("WhatsApp Audio 2026-08-12 at 13.11.09", "WhatsApp Audio", True, None),
        ("PTT-20260812-WA0001", "WhatsApp Voice Notes", True, 1),
        ("audio_2026-08-12_13-11-09", "Telegram Audio", True, None),
        ("signal-2026-08-12-131109", "Signal", True, None),
        ("ZOOM0001", "Zoom Recorder", False, 1),
        ("VOICE002", "Philips VoiceTracer", False, 2),
        ("TASCAM_0003", "Tascam", False, 3),
        ("R20260812-131109", "Device Recorder", True, None),
        ("Recording_20260812_131109", "Android Recorder", True, None),
    ],
)
def test_parse_voice_note_stem_families(
    stem: str, family: str, has_dt: bool, sequence: int | None
) -> None:
    parsed = parse_voice_note_stem(stem)
    assert parsed is not None
    assert parsed[0] == family
    assert (parsed[1] is not None) is has_dt
    assert parsed[2] == sequence


@pytest.mark.unit
def test_parse_voice_note_stem_rejects_generic_meeting_names() -> None:
    assert parse_voice_note_stem("meeting_01") is None
    assert parse_voice_note_stem("260223_team_facilitation_10") is None
    assert parse_voice_note_stem("plain_name") is None
