"""Tests for permanently dismissed Auto-merge suggestions."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.audio.merge_dismissals import (
    add_permanently_dismissed_key,
    dismissed_path,
    filter_permanently_dismissed,
    load_permanently_dismissed_keys,
    remove_permanently_dismissed_key,
    save_permanently_dismissed_keys,
    serial_group_dismissal_key,
)
from transcriptx.core.audio.serial_groups import SerialGroup


def test_save_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "audio_merge_dismissed.json"
    save_permanently_dismissed_keys(
        ["numeric_index:foo", "voice_note_run:WhatsApp 2026-08-12"],
        path=path,
    )
    assert load_permanently_dismissed_keys(path=path) == [
        "numeric_index:foo",
        "voice_note_run:WhatsApp 2026-08-12",
    ]


def test_add_is_idempotent_and_preserves_order(tmp_path: Path) -> None:
    path = tmp_path / "audio_merge_dismissed.json"
    add_permanently_dismissed_key("a:one", path=path)
    add_permanently_dismissed_key("b:two", path=path)
    add_permanently_dismissed_key("a:one", path=path)
    assert load_permanently_dismissed_keys(path=path) == ["a:one", "b:two"]


def test_remove_missing_key_is_noop(tmp_path: Path) -> None:
    path = tmp_path / "audio_merge_dismissed.json"
    add_permanently_dismissed_key("keep:me", path=path)
    remove_permanently_dismissed_key("gone:already", path=path)
    assert load_permanently_dismissed_keys(path=path) == ["keep:me"]
    remove_permanently_dismissed_key("keep:me", path=path)
    assert load_permanently_dismissed_keys(path=path) == []


def test_missing_or_invalid_file_is_empty(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    assert load_permanently_dismissed_keys(path=missing) == []
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_permanently_dismissed_keys(path=bad) == []


def test_dismissed_path_uses_config_dir(tmp_path: Path) -> None:
    assert dismissed_path(tmp_path) == tmp_path / "audio_merge_dismissed.json"


def test_filter_drops_matching_groups() -> None:
    keep = SerialGroup(
        base_key="keep",
        ordered_paths=(Path("/a.wav"), Path("/b.wav")),
        confidence="high",
        matched_rule="part_suffix",
    )
    drop = SerialGroup(
        base_key="drop",
        ordered_paths=(Path("/c.wav"), Path("/d.wav")),
        confidence="high",
        matched_rule="numeric_index",
    )
    kept = filter_permanently_dismissed(
        [keep, drop], dismissed_keys=["numeric_index:drop"]
    )
    assert kept == [keep]


def test_lite_group_key_fallback() -> None:
    class _Lite:
        base_key = "meeting"
        matched_rule = "part_suffix"

    assert serial_group_dismissal_key(_Lite()) == "part_suffix:meeting"
