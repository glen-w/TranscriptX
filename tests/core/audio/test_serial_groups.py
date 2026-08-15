"""Tests for serial groups."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.audio.serial_groups import (
    SerialDetectionConfig,
    detect_serial_audio_groups,
    merged_output_filename,
    partition_dismissed_serial_groups,
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

    def test_bare_timestamp_plus_hyphen_continuation(self) -> None:
        paths = [
            _p("20260619172327.wav"),
            _p("20260619172327-01.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        group = groups[0]
        assert group.matched_rule == "timestamp_suffix"
        assert group.confidence == "high"
        assert group.base_key == "20260619172327"
        assert group.indices == (0, 1)
        assert [p.name for p in group.ordered_paths] == [
            "20260619172327.wav",
            "20260619172327-01.wav",
        ]

    def test_bare_timestamp_plus_underscore_continuation(self) -> None:
        paths = [
            _p("20260619172327_01.wav"),
            _p("20260619172327.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert [p.name for p in groups[0].ordered_paths] == [
            "20260619172327.wav",
            "20260619172327_01.wav",
        ]

    def test_bare_timestamp_alone_is_not_a_group(self) -> None:
        assert detect_serial_audio_groups([_p("20260619172327.wav")]) == []

    def test_unrelated_bare_timestamps_are_not_grouped(self) -> None:
        paths = [
            _p("20260619172327.wav"),
            _p("20260619172328.wav"),
        ]
        assert detect_serial_audio_groups(paths) == []

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


class TestVoiceNoteRunGrouping:
    def test_clusters_whatsapp_burst_and_splits_later_notes(self) -> None:
        paths = [
            _p("WhatsApp Audio 2026-08-12 at 13.11.09.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 13.20.50.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 13.21.35.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 13.41.29.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 13.45.31.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 13.55.04.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 13.58.02.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 15.22.37.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 17.23.50.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 17.30.12.mp3"),
            _p("WhatsApp Audio 2026-08-13 at 18.09.36.mp3"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert [g.matched_rule for g in groups] == ["voice_note_run", "voice_note_run"]
        names = [[p.name for p in g.ordered_paths] for g in groups]
        assert names[0] == [
            "WhatsApp Audio 2026-08-12 at 13.11.09.mp3",
            "WhatsApp Audio 2026-08-12 at 13.20.50.mp3",
            "WhatsApp Audio 2026-08-12 at 13.21.35.mp3",
            "WhatsApp Audio 2026-08-12 at 13.41.29.mp3",
            "WhatsApp Audio 2026-08-12 at 13.45.31.mp3",
            "WhatsApp Audio 2026-08-12 at 13.55.04.mp3",
            "WhatsApp Audio 2026-08-12 at 13.58.02.mp3",
        ]
        assert names[1] == [
            "WhatsApp Audio 2026-08-12 at 17.23.50.mp3",
            "WhatsApp Audio 2026-08-12 at 17.30.12.mp3",
        ]
        assert groups[0].base_key == "WhatsApp Audio 2026-08-12 13:11:09"
        assert groups[0].rule_label == "voice note run"

    def test_does_not_group_notes_hours_apart(self) -> None:
        paths = [
            _p("WhatsApp Audio 2026-08-12 at 13.58.02.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 15.22.37.mp3"),
        ]
        assert detect_serial_audio_groups(paths) == []

    def test_does_not_mix_voice_note_families(self) -> None:
        paths = [
            _p("WhatsApp Audio 2026-08-12 at 13.11.09.mp3"),
            _p("Voice Note 2026-08-12 at 13.12.09.mp3"),
        ]
        assert detect_serial_audio_groups(paths) == []

    def test_respects_custom_gap(self) -> None:
        paths = [
            _p("WhatsApp Audio 2026-08-12 at 13.11.09.mp3"),
            _p("WhatsApp Audio 2026-08-12 at 13.41.29.mp3"),
        ]
        assert detect_serial_audio_groups(
            paths, config=SerialDetectionConfig(voice_note_max_gap_seconds=60)
        ) == []
        groups = detect_serial_audio_groups(
            paths, config=SerialDetectionConfig(voice_note_max_gap_seconds=40 * 60)
        )
        assert len(groups) == 1
        assert len(groups[0].ordered_paths) == 2

    def test_clusters_telegram_desktop_saves(self) -> None:
        paths = [
            _p("audio_2026-08-12_13-11-09.ogg"),
            _p("audio_2026-08-12_13-20-50.ogg"),
            _p("audio_2026-08-12_15-22-37.ogg"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].matched_rule == "voice_note_run"
        assert groups[0].base_key == "Telegram Audio 2026-08-12 13:11:09"
        assert [p.name for p in groups[0].ordered_paths] == [
            "audio_2026-08-12_13-11-09.ogg",
            "audio_2026-08-12_13-20-50.ogg",
        ]

    def test_clusters_signal_saves(self) -> None:
        paths = [
            _p("signal-2026-08-12-131109.aac"),
            _p("signal-2026-08-12-13-20-50-88.aac"),
            _p("signal-2026-08-12-17-23-50.aac"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].base_key == "Signal 2026-08-12 13:11:09"
        assert [p.name for p in groups[0].ordered_paths] == [
            "signal-2026-08-12-131109.aac",
            "signal-2026-08-12-13-20-50-88.aac",
        ]

    def test_clusters_whatsapp_android_ptt_same_day(self) -> None:
        paths = [
            _p("PTT-20260812-WA0001.opus"),
            _p("PTT-20260812-WA0002.opus"),
            _p("PTT-20260812-WA0004.opus"),
            _p("PTT-20260813-WA0001.opus"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].base_key == "WhatsApp Voice Notes 2026-08-12"
        assert [p.name for p in groups[0].ordered_paths] == [
            "PTT-20260812-WA0001.opus",
            "PTT-20260812-WA0002.opus",
            "PTT-20260812-WA0004.opus",
        ]

    def test_clusters_instagram_helper_exports(self) -> None:
        paths = [
            _p("Instagram-audio-2026-08-12 13-11-09.mp4"),
            _p("Instagram-audio-2026-08-12 13-20-50.mp4"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].base_key.startswith("Instagram Audio")

    def test_does_not_mix_apps(self) -> None:
        paths = [
            _p("audio_2026-08-12_13-11-09.ogg"),
            _p("signal-2026-08-12-131109.aac"),
        ]
        assert detect_serial_audio_groups(paths) == []

    def test_clusters_zoom_default_sequence(self) -> None:
        paths = [
            _p("ZOOM0001.WAV"),
            _p("ZOOM0002.WAV"),
            _p("ZOOM0003.WAV"),
            _p("ZOOM0010.WAV"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].matched_rule == "voice_note_run"
        assert groups[0].base_key == "Zoom Recorder 1"
        assert [p.name for p in groups[0].ordered_paths] == [
            "ZOOM0001.WAV",
            "ZOOM0002.WAV",
            "ZOOM0003.WAV",
        ]

    def test_clusters_zoom_date_mode_burst(self) -> None:
        paths = [
            _p("240115-092530.WAV"),
            _p("240115-093015.WAV"),
            _p("240115-120000.WAV"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].base_key == "Zoom Recorder 2024-01-15 09:25:30"
        assert [p.name for p in groups[0].ordered_paths] == [
            "240115-092530.WAV",
            "240115-093015.WAV",
        ]

    def test_clusters_android_recording_burst(self) -> None:
        paths = [
            _p("Recording_20260812_131109.m4a"),
            _p("Recording_20260812_132050.m4a"),
            _p("Recording_20260812_152237.m4a"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].base_key == "Android Recorder 2026-08-12 13:11:09"
        assert [p.name for p in groups[0].ordered_paths] == [
            "Recording_20260812_131109.m4a",
            "Recording_20260812_132050.m4a",
        ]

    def test_clusters_philips_voicetracer_sequence(self) -> None:
        paths = [
            _p("VOICE001.mp3"),
            _p("VOICE002.mp3"),
            _p("VOICE003.mp3"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].base_key == "Philips VoiceTracer 1"
        assert [p.name for p in groups[0].ordered_paths] == [
            "VOICE001.mp3",
            "VOICE002.mp3",
            "VOICE003.mp3",
        ]

    def test_clusters_sony_icd_and_device_r_prefix(self) -> None:
        sony = [
            _p("161010_0706.mp3"),
            _p("161010_0715.mp3"),
            _p("161010_1200.mp3"),
        ]
        sony_groups = detect_serial_audio_groups(sony)
        assert len(sony_groups) == 1
        assert sony_groups[0].base_key == "Sony ICD 2016-10-10 07:06:00"

        device = [
            _p("R20260812-131109.wav"),
            _p("R20260812-132050.wav"),
        ]
        device_groups = detect_serial_audio_groups(device)
        assert len(device_groups) == 1
        assert device_groups[0].base_key == "Device Recorder 2026-08-12 13:11:09"

    def test_does_not_mix_zoom_seq_with_date_mode(self) -> None:
        paths = [
            _p("ZOOM0001.WAV"),
            _p("240115-092530.WAV"),
        ]
        assert detect_serial_audio_groups(paths) == []

    def test_clusters_tascam_sequence(self) -> None:
        paths = [
            _p("TASCAM_0001.wav"),
            _p("TASCAM_0002.wav"),
            _p("TASCAM_0004.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].matched_rule == "voice_note_run"
        assert groups[0].base_key == "Tascam 1"
        assert [p.name for p in groups[0].ordered_paths] == [
            "TASCAM_0001.wav",
            "TASCAM_0002.wav",
            "TASCAM_0004.wav",
        ]

    def test_voice_note_rule_wins_over_numeric_false_serial(self) -> None:
        """Zoom/device stems must not fall through as generic numeric_index groups."""
        paths = [
            _p("ZOOM0001.WAV"),
            _p("ZOOM0002.WAV"),
            _p("260223_team_facilitation_10.mp3"),
            _p("260223_team_facilitation_11.mp3"),
        ]
        groups = detect_serial_audio_groups(paths)
        by_rule = {g.matched_rule: g for g in groups}
        assert set(by_rule) == {"voice_note_run", "numeric_index"}
        assert by_rule["voice_note_run"].base_key == "Zoom Recorder 1"
        assert [p.name for p in by_rule["voice_note_run"].ordered_paths] == [
            "ZOOM0001.WAV",
            "ZOOM0002.WAV",
        ]
        assert by_rule["numeric_index"].base_key == "260223_team_facilitation"


class TestDismissalPartition:
    def test_dismissal_key_is_rule_and_stem(self) -> None:
        paths = [
            _p("260223_team_facilitation_10.mp3"),
            _p("260223_team_facilitation_11.mp3"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert groups[0].dismissal_key == "numeric_index:260223_team_facilitation"

    def test_partition_hides_matching_stem(self) -> None:
        paths = [
            _p("260223_team_facilitation_10.mp3"),
            _p("260223_team_facilitation_11.mp3"),
            _p("20251230160235_1.wav"),
            _p("20251230160235_2.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        visible, hidden = partition_dismissed_serial_groups(
            groups, ["numeric_index:260223_team_facilitation"]
        )
        assert [g.base_key for g in hidden] == ["260223_team_facilitation"]
        assert [g.base_key for g in visible] == ["20251230160235"]

    def test_dismissal_survives_extra_numbered_session(self) -> None:
        first = detect_serial_audio_groups(
            [
                _p("260223_team_facilitation_10.mp3"),
                _p("260223_team_facilitation_11.mp3"),
            ]
        )
        later = detect_serial_audio_groups(
            [
                _p("260223_team_facilitation_10.mp3"),
                _p("260223_team_facilitation_11.mp3"),
                _p("260223_team_facilitation_12.mp3"),
            ]
        )
        assert first[0].dismissal_key == later[0].dismissal_key


class TestMergedOutputFilename:
    def test_merged_output_filename_format(self) -> None:
        assert merged_output_filename("20251230160235") == "20251230160235_merged.mp3"
        assert merged_output_filename("meeting") == "meeting_merged.mp3"
        assert merged_output_filename("REC") == "REC_merged.mp3"
