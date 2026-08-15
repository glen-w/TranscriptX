"""Tests for merge source profiles and configurable grouping windows."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from transcriptx.core.audio.merge_profiles import (
    GroupingSpec,
    MatchSpec,
    MergeSourceProfile,
    builtin_merge_source_profiles,
    family_matches,
    load_merge_source_profiles,
    reset_builtin_profile,
    save_merge_source_profiles,
    validate_profiles_payload,
)
from transcriptx.core.audio.serial_groups import (
    detect_merge_groups,
    detect_serial_audio_groups,
)


def _p(name: str) -> Path:
    return Path("/tmp/recordings") / name


def _whatsapp_profile(**grouping: float | int) -> MergeSourceProfile:
    base = next(p for p in builtin_merge_source_profiles() if p.id == "whatsapp")
    return replace(
        base,
        grouping=GroupingSpec(
            mode="time_window",
            same_day_days=int(grouping.get("same_day_days", 0)),
            max_gap_hours=float(grouping.get("max_gap_hours", 20.0 / 60.0)),
        ),
    )


def _telegram_profile(**grouping: float | int) -> MergeSourceProfile:
    base = next(p for p in builtin_merge_source_profiles() if p.id == "telegram")
    return replace(
        base,
        grouping=GroupingSpec(
            mode="time_window",
            same_day_days=int(grouping.get("same_day_days", 0)),
            max_gap_hours=float(grouping.get("max_gap_hours", 20.0 / 60.0)),
        ),
    )


def _zoom_profile(**grouping: float | int) -> MergeSourceProfile:
    base = next(p for p in builtin_merge_source_profiles() if p.id == "zoom_recorder")
    return replace(
        base,
        grouping=GroupingSpec(
            mode="time_window",
            same_day_days=int(grouping.get("same_day_days", 0)),
            max_gap_hours=float(grouping.get("max_gap_hours", 20.0 / 60.0)),
        ),
    )


class TestFamilyMatches:
    def test_prefix_and_exact(self) -> None:
        assert family_matches("WhatsApp Audio", ["WhatsApp"])
        assert family_matches("WhatsApp Voice Notes", ["WhatsApp Voice Notes"])
        assert not family_matches("Telegram Audio", ["WhatsApp"])


class TestBuiltinDefaultsMatchLegacy:
    def test_default_whatsapp_still_splits_hour_gap(self) -> None:
        paths = [
            _p("WhatsApp Audio 2026-08-12 at 13.58.02.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 15.22.37.mp3"),
        ]
        assert detect_serial_audio_groups(paths) == []
        assert detect_merge_groups(paths) == []


class TestConfigurableWindows:
    def test_whatsapp_two_hour_same_day_merges_example_burst(self) -> None:
        paths = [
            _p("WhatsApp Audio 2026-08-12 at 13.11.09.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 13.58.02.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 15.22.37.mp3"),
        ]
        # Default 20 minutes: only the first two are within gap of each other?
        # 13:11 to 13:58 is 47 minutes → default splits everything to empty/partial.
        assert detect_merge_groups(paths) == []

        profile = _whatsapp_profile(same_day_days=1, max_gap_hours=2.0)
        groups = detect_merge_groups(paths, profiles=[profile])
        assert len(groups) == 1
        assert [p.name for p in groups[0].ordered_paths] == [
            "WhatsApp Audio 2026-08-12 at 13.11.09.mp3",
            "WhatsApp Audio 2026-08-12 at 13.58.02.mp3",
            "WhatsApp Audio 2026-08-12 at 15.22.37.mp3",
        ]
        assert groups[0].profile_id == "whatsapp"

    def test_telegram_six_hour_same_day(self) -> None:
        paths = [
            _p("audio_2026-08-12_13-11-09.ogg"),
            _p("audio_2026-08-12_15-22-37.ogg"),
            _p("audio_2026-08-12_20-00-00.ogg"),
        ]
        assert detect_merge_groups(paths) == []  # default 20 min

        profile = _telegram_profile(same_day_days=1, max_gap_hours=6.0)
        groups = detect_merge_groups(paths, profiles=[profile])
        assert len(groups) == 1
        assert len(groups[0].ordered_paths) == 3

    def test_zoom_full_day_unlimited_gap(self) -> None:
        paths = [
            _p("240115-092530.WAV"),
            _p("240115-120000.WAV"),
            _p("240115-180000.WAV"),
        ]
        assert detect_merge_groups(paths) == []  # default 20 min

        profile = _zoom_profile(same_day_days=1, max_gap_hours=0.0)
        groups = detect_merge_groups(paths, profiles=[profile])
        assert len(groups) == 1
        assert [p.name for p in groups[0].ordered_paths] == [
            "240115-092530.WAV",
            "240115-120000.WAV",
            "240115-180000.WAV",
        ]

    def test_user_regex_profile(self) -> None:
        paths = [
            _p("audio_2026-08-12_10-00-00.ogg"),
            _p("audio_2026-08-12_10-15-00.ogg"),
            _p("signal-2026-08-12-100500.aac"),
        ]
        profile = MergeSourceProfile(
            id="calls",
            name="Calls",
            enabled=True,
            builtin=False,
            match=MatchSpec(kind="filename_regex", patterns=(r"^audio_",)),
            grouping=GroupingSpec(
                mode="time_window", same_day_days=1, max_gap_hours=1.0
            ),
            priority=50,
        )
        groups = detect_merge_groups(paths, profiles=[profile])
        assert len(groups) == 1
        assert [p.name for p in groups[0].ordered_paths] == [
            "audio_2026-08-12_10-00-00.ogg",
            "audio_2026-08-12_10-15-00.ogg",
        ]


class TestSafeguardsAndPriority:
    def test_skips_merged_outputs(self) -> None:
        paths = [
            _p("20251230160235_1.wav"),
            _p("20251230160235_2.wav"),
            _p("20251230160235_merged.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 13.11.09_merged.mp3"),
        ]
        groups = detect_merge_groups(paths)
        assert len(groups) == 1
        assert all("_merged" not in p.name for g in groups for p in g.ordered_paths)

    def test_profile_priority_serial_before_regex(self) -> None:
        paths = [
            _p("meeting_part1.mp3"),
            _p("meeting_part2.mp3"),
        ]
        serial = next(
            p for p in builtin_merge_source_profiles() if p.id == "serial_parts"
        )
        regex = MergeSourceProfile(
            id="meeting_regex",
            name="Meeting regex",
            enabled=True,
            builtin=False,
            match=MatchSpec(kind="filename_regex", patterns=(r"meeting",)),
            grouping=GroupingSpec(
                mode="time_window", same_day_days=0, max_gap_hours=0.0
            ),
            priority=1,  # higher priority number loses; lower wins — set lower than serial? serial is 10
        )
        # Give regex lower priority number so it would win if it produced a group,
        # but serial rule confidence/order should still claim part suffixes.
        regex = replace(regex, priority=5)
        groups = detect_merge_groups(paths, profiles=[serial, regex])
        assert len(groups) == 1
        assert groups[0].matched_rule == "part_suffix"
        assert groups[0].profile_id == "serial_parts"

    def test_same_day_days_multi_day_window(self) -> None:
        paths = [
            _p("WhatsApp Audio 2026-08-12 at 13.11.09.mp3"),
            _p("WhatsApp Audio 2026-08-13 at 13.15.00.mp3"),
        ]
        # same day only → no group (different days, 20 min wouldn't matter across days for gap alone
        # but consecutive gap across days is large anyway)
        assert detect_merge_groups(paths) == []

        profile = _whatsapp_profile(same_day_days=2, max_gap_hours=48.0)
        groups = detect_merge_groups(paths, profiles=[profile])
        assert len(groups) == 1
        assert len(groups[0].ordered_paths) == 2


class TestPersistence:
    def test_save_load_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "audio_merge_profiles.json"
        profile = _whatsapp_profile(same_day_days=1, max_gap_hours=2.0)
        others = [p for p in builtin_merge_source_profiles() if p.id != "whatsapp"]
        save_merge_source_profiles([profile, *others], path=path)
        loaded = load_merge_source_profiles(path=path)
        whatsapp = next(p for p in loaded if p.id == "whatsapp")
        assert whatsapp.grouping.same_day_days == 1
        assert whatsapp.grouping.max_gap_hours == 2.0
        assert whatsapp.builtin is True

    def test_missing_builtin_is_readded(self, tmp_path: Path) -> None:
        path = tmp_path / "audio_merge_profiles.json"
        only = [p for p in builtin_merge_source_profiles() if p.id == "whatsapp"]
        save_merge_source_profiles(only, path=path)
        loaded = load_merge_source_profiles(path=path)
        ids = {p.id for p in loaded}
        assert "serial_parts" in ids
        assert "telegram" in ids

    def test_reset_builtin(self) -> None:
        edited = _whatsapp_profile(same_day_days=1, max_gap_hours=6.0)
        reset = reset_builtin_profile([edited], "whatsapp")
        whatsapp = next(p for p in reset if p.id == "whatsapp")
        assert whatsapp.grouping.max_gap_hours == pytest.approx(20.0 / 60.0)

    def test_validate_rejects_bad_regex(self) -> None:
        with pytest.raises(Exception):
            validate_profiles_payload(
                [
                    {
                        "id": "bad",
                        "name": "Bad",
                        "match": {"kind": "filename_regex", "patterns": ["("]},
                        "grouping": {"mode": "time_window"},
                    }
                ]
            )
