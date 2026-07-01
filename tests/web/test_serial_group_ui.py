from __future__ import annotations

from pathlib import Path

from transcriptx.core.audio.serial_groups import detect_serial_audio_groups
from transcriptx.web.navigation import (
    TRANSCRIPTION_NAV_PATHS_KEY,
    consume_transcription_nav_paths,
    navigate_to_audio_merge_with_paths,
    navigate_to_transcribe_with_paths,
)


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


class TestPageIntegrationPresence:
    def test_transcribe_audio_is_external_instructions(self) -> None:
        import transcriptx.web.page_modules.transcribe_audio as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "whispermlx-missing" in source
        assert "Import Transcript" in source
        assert "consume_transcription_nav_paths" in source

    def test_audio_merge_links_to_transcribe_instructions(self) -> None:
        import transcriptx.web.page_modules.audio_merge as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "_render_detected_serial_groups" in source
        assert "Detected serial recordings" in source
        assert "Use this group" in source
        assert "How to transcribe this file" in source
        assert "navigate_to_transcribe_with_paths" in source

    def test_serial_group_prompt_component_exists(self) -> None:
        import transcriptx.web.components.serial_group_prompt as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "render_serial_group_prompt" in source
        assert "Transcribe these files separately anyway" in source
