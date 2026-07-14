"""Tests for serial groups."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.audio.serial_groups import (
    SerialDetectionConfig,
    detect_serial_audio_groups,
    merged_output_filename,
)


def _p(name: str) -> Path:
    return Path("/tmp/recordings") / name


class TestTimestampSuffixGrouping:
    def test_groups_timestamp_suffix_files(self) -> None:
        paths = [
            _p("20251230160235_1.wav"),
            _p("20251230160235_2.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        group = groups[0]
        assert group.matched_rule == "timestamp_suffix"
        assert group.confidence == "high"
        assert group.base_key == "20251230160235"
        assert [p.name for p in group.ordered_paths] == [
            "20251230160235_1.wav",
            "20251230160235_2.wav",
        ]

    def test_zero_padded_timestamp_suffix(self) -> None:
        paths = [
            _p("20251230160235_03.wav"),
            _p("20251230160235_1.wav"),
            _p("20251230160235_2.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert [idx for idx in groups[0].indices] == [1, 2, 3]

    def test_hyphen_timestamp_suffix(self) -> None:
        paths = [
            _p("20251230160235-1.wav"),
            _p("20251230160235-4.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].matched_rule == "timestamp_suffix"
        assert groups[0].indices == (1, 4)

    def test_natural_order_not_alphabetical(self) -> None:
        paths = [
            _p("20251230160235_10.wav"),
            _p("20251230160235_1.wav"),
            _p("20251230160235_2.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert [p.name for p in groups[0].ordered_paths] == [
            "20251230160235_1.wav",
            "20251230160235_2.wav",
            "20251230160235_10.wav",
        ]


class TestPartSuffixGrouping:
    def test_groups_part_suffix_files(self) -> None:
        paths = [
            _p("meeting_part1.mp3"),
            _p("meeting_part2.mp3"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].matched_rule == "part_suffix"
        assert groups[0].base_key == "meeting"

    def test_part_suffix_with_spaces_and_hyphens(self) -> None:
        paths = [
            _p("meeting-part-03.mp3"),
            _p("meeting part 4.mp3"),
            _p("meeting_part1.mp3"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].indices == (1, 3, 4)


class TestNumericIndexGrouping:
    def test_groups_zero_padded_numeric_index(self) -> None:
        paths = [
            _p("REC_001.wav"),
            _p("REC_002.wav"),
            _p("REC_010.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].matched_rule == "numeric_index"
        assert groups[0].confidence == "medium"
        assert groups[0].base_key == "REC"
        assert groups[0].indices == (1, 2, 10)


class TestDuplicateSuffixGrouping:
    def test_groups_finder_duplicate_suffix(self) -> None:
        paths = [
            _p("recording.wav"),
            _p("recording (1).wav"),
            _p("recording (2).wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].matched_rule == "duplicate_suffix"
        assert groups[0].indices == (0, 1, 2)
        assert groups[0].ordered_paths[0].name == "recording.wav"


class TestSafeguards:
    def test_mixed_extensions_not_grouped(self) -> None:
        paths = [
            _p("20251230160235_1.wav"),
            _p("20251230160235_2.mp3"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert groups == []

    def test_mixed_extensions_allowed_when_disabled(self) -> None:
        paths = [
            _p("20251230160235_1.wav"),
            _p("20251230160235_2.mp3"),
        ]
        config = SerialDetectionConfig(require_same_extension=False)
        groups = detect_serial_audio_groups(paths, config=config)
        assert len(groups) == 1

    def test_unrelated_files_not_grouped(self) -> None:
        paths = [
            _p("alpha_1.wav"),
            _p("beta_2.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert groups == []

    def test_min_group_size_ignored(self) -> None:
        paths = [_p("20251230160235_1.wav")]
        groups = detect_serial_audio_groups(paths)
        assert groups == []

        config = SerialDetectionConfig(min_group_size=3)
        paths = [
            _p("20251230160235_1.wav"),
            _p("20251230160235_2.wav"),
        ]
        groups = detect_serial_audio_groups(paths, config=config)
        assert groups == []

    def test_disabled_config_returns_empty(self) -> None:
        paths = [
            _p("20251230160235_1.wav"),
            _p("20251230160235_2.wav"),
        ]
        config = SerialDetectionConfig(enabled=False)
        assert detect_serial_audio_groups(paths, config=config) == []

    def test_path_cannot_appear_in_more_than_one_group(self) -> None:
        paths = [
            _p("meeting_part1.mp3"),
            _p("meeting_part2.mp3"),
            _p("20251230160235_1.wav"),
            _p("20251230160235_2.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        all_paths = [p for g in groups for p in g.ordered_paths]
        assert len(all_paths) == len(set(all_paths))
        assert len(groups) == 2

    def test_large_index_gap_creates_warning(self) -> None:
        paths = [
            _p("20251230160235_1.wav"),
            _p("20251230160235_10.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].warnings
        assert "gap" in groups[0].warnings[0].lower()

    def test_final_group_ordering_is_deterministic(self) -> None:
        paths = [
            _p("20251230160235_1.wav"),
            _p("20251230160235_2.wav"),
            _p("meeting_part1.mp3"),
            _p("meeting_part2.mp3"),
        ]
        first = detect_serial_audio_groups(paths)
        second = detect_serial_audio_groups(list(reversed(paths)))
        assert [g.base_key for g in first] == [g.base_key for g in second]


class TestMergedOutputFilename:
    def test_merged_output_filename_format(self) -> None:
        assert merged_output_filename("20251230160235") == "20251230160235_merged.mp3"
        assert merged_output_filename("meeting") == "meeting_merged.mp3"
        assert merged_output_filename("REC") == "REC_merged.mp3"
