from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.app.models.results import MergeResult
from transcriptx.core.audio.serial_groups import SerialGroup, detect_serial_audio_groups
from transcriptx.web.navigation import (
    TRANSCRIPTION_NAV_PATHS_KEY,
    consume_transcription_nav_paths,
    navigate_to_audio_merge_with_paths,
    navigate_to_transcribe_with_paths,
)
from transcriptx.web.page_modules.transcribe_audio import (
    replace_grouped_paths_with_merged,
)


def _group(base_key: str, names: list[str]) -> SerialGroup:
    paths = tuple(Path("/tmp") / name for name in names)
    return SerialGroup(
        base_key=base_key,
        ordered_paths=paths,
        confidence="high",
        matched_rule="timestamp_suffix",
        indices=tuple(range(1, len(names) + 1)),
    )


class TestReplaceGroupedPathsWithMerged:
    def test_replaces_group_and_preserves_ungrouped(self) -> None:
        a1 = Path("/tmp/a_1.wav")
        a2 = Path("/tmp/a_2.wav")
        b = Path("/tmp/b.wav")
        merged = Path("/tmp/a_merged.mp3")
        groups = [_group("a", ["a_1.wav", "a_2.wav"])]
        result = replace_grouped_paths_with_merged(
            [a1, a2, b],
            groups,
            {"a": merged},
        )
        assert result == [merged, b]

    def test_preserves_input_order_for_multiple_groups(self) -> None:
        g1_paths = [Path("/tmp/s1_1.wav"), Path("/tmp/s1_2.wav")]
        g2_paths = [Path("/tmp/s2_1.wav"), Path("/tmp/s2_2.wav")]
        lone = Path("/tmp/lone.wav")
        merged1 = Path("/tmp/s1_merged.mp3")
        merged2 = Path("/tmp/s2_merged.mp3")
        groups = [
            _group("s1", ["s1_1.wav", "s1_2.wav"]),
            _group("s2", ["s2_1.wav", "s2_2.wav"]),
        ]
        result = replace_grouped_paths_with_merged(
            [g1_paths[0], lone, g2_paths[0], g1_paths[1], g2_paths[1]],
            groups,
            {"s1": merged1, "s2": merged2},
        )
        assert result == [merged1, lone, merged2]


class TestNavigationHelpers:
    def test_navigate_to_audio_merge_with_paths(self) -> None:
        session: dict = {}
        navigate_to_audio_merge_with_paths(
            session, [Path("/tmp/a_1.wav"), Path("/tmp/a_2.wav")]
        )
        assert session["page"] == "Audio Merge"
        assert session["audio_merge_ordered_paths"] == [
            "/tmp/a_1.wav",
            "/tmp/a_2.wav",
        ]

    def test_navigate_to_transcribe_with_paths(self) -> None:
        session: dict = {}
        navigate_to_transcribe_with_paths(session, [Path("/tmp/merged.mp3")])
        assert session["page"] == "Transcribe Audio"
        assert session["transcription_active_tab"] == "Pick existing"
        assert session[TRANSCRIPTION_NAV_PATHS_KEY] == ["/tmp/merged.mp3"]

    def test_consume_transcription_nav_paths_one_shot(self) -> None:
        session = {TRANSCRIPTION_NAV_PATHS_KEY: ["/tmp/merged.mp3"]}
        assert consume_transcription_nav_paths(session) == ["/tmp/merged.mp3"]
        assert TRANSCRIPTION_NAV_PATHS_KEY not in session


class TestSerialDetectionIntegration:
    def test_detects_group_for_transcribe_selection(self) -> None:
        paths = [
            Path("/rec/20251230160235_1.wav"),
            Path("/rec/20251230160235_2.wav"),
            Path("/rec/interview.wav"),
        ]
        groups = detect_serial_audio_groups(paths)
        assert len(groups) == 1
        assert len(groups[0].ordered_paths) == 2

    def test_no_group_for_unrelated_selection(self) -> None:
        paths = [Path("/rec/a.wav"), Path("/rec/b.wav")]
        assert detect_serial_audio_groups(paths) == []


class TestMergeSerialGroups:
    @pytest.mark.unit
    @patch("transcriptx.web.page_modules.transcribe_audio.MergeController")
    @patch("transcriptx.web.page_modules.transcribe_audio.st")
    def test_merge_serial_groups_success(self, mock_st, mock_ctrl_cls) -> None:
        from transcriptx.web.page_modules.transcribe_audio import _merge_serial_groups

        merged_path = Path("/tmp/20251230160235_merged.mp3")
        mock_ctrl = mock_ctrl_cls.return_value
        mock_ctrl.run_merge.return_value = MergeResult(
            success=True,
            output_path=merged_path,
            files_merged=2,
        )
        mock_st.session_state = {}

        groups = [
            _group("20251230160235", ["20251230160235_1.wav", "20251230160235_2.wav"])
        ]
        outputs, failure = _merge_serial_groups(
            groups, progress_snapshot_key="merge_snap"
        )

        assert failure is None
        assert outputs == {"20251230160235": merged_path}
        mock_ctrl.run_merge.assert_called_once()
        request = mock_ctrl.run_merge.call_args[0][0]
        assert request.output_filename == "20251230160235_merged.mp3"

    @pytest.mark.unit
    @patch("transcriptx.web.page_modules.transcribe_audio.MergeController")
    @patch("transcriptx.web.page_modules.transcribe_audio.st")
    def test_merge_serial_groups_failure_stops(self, mock_st, mock_ctrl_cls) -> None:
        from transcriptx.web.page_modules.transcribe_audio import _merge_serial_groups

        mock_ctrl = mock_ctrl_cls.return_value
        mock_ctrl.run_merge.return_value = MergeResult(
            success=False,
            errors=["ffmpeg missing"],
        )
        mock_st.session_state = {}

        groups = [
            _group("20251230160235", ["20251230160235_1.wav", "20251230160235_2.wav"])
        ]
        outputs, failure = _merge_serial_groups(
            groups, progress_snapshot_key="merge_snap"
        )

        assert outputs == {}
        assert failure is not None
        assert failure.errors == ["ffmpeg missing"]


class TestPageIntegrationPresence:
    def test_transcribe_audio_uses_serial_detection(self) -> None:
        import transcriptx.web.page_modules.transcribe_audio as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "detect_serial_audio_groups" in source
        assert "render_serial_group_prompt" in source
        assert "replace_grouped_paths_with_merged" in source
        assert "transcription_serial_separate_ok" in source
        assert "_KEY_MERGE_BUTTON" in source
        assert "_merge_serial_groups" in source

    def test_audio_merge_shows_detected_groups(self) -> None:
        import transcriptx.web.page_modules.audio_merge as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "_render_detected_serial_groups" in source
        assert "Detected serial recordings" in source
        assert "Use this group" in source
        assert "Transcribe merged file" in source
        assert "navigate_to_transcribe_with_paths" in source

    def test_serial_group_prompt_component_exists(self) -> None:
        import transcriptx.web.components.serial_group_prompt as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "render_serial_group_prompt" in source
        assert "Transcribe these files separately anyway" in source
