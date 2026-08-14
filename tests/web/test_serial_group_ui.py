"""Tests for serial group UI helpers and Tools merge navigation."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.audio.serial_groups import detect_serial_audio_groups
from transcriptx.web.navigation import (
    TRANSCRIPTION_NAV_PATHS_KEY,
    consume_transcription_nav_paths,
    navigate_to_transcribe_with_paths,
)
from transcriptx.web.ui.tools.merge_panel import (
    hide_serial_group_in_session,
    hidden_serial_keys_from_session,
    restore_serial_group_in_session,
)


class TestNavigationHelpers:
    def test_navigate_to_transcribe_with_paths(self) -> None:
        session: dict = {}
        navigate_to_transcribe_with_paths(session, [Path("/tmp/merged.mp3")])
        assert session["page"] == "Transcribe Audio"
        assert session[TRANSCRIPTION_NAV_PATHS_KEY] == ["/tmp/merged.mp3"]

    def test_consume_transcription_nav_paths_one_shot(self) -> None:
        session = {TRANSCRIPTION_NAV_PATHS_KEY: ["/tmp/merged.mp3"]}
        assert consume_transcription_nav_paths(session) == ["/tmp/merged.mp3"]
        assert TRANSCRIPTION_NAV_PATHS_KEY not in session

    def test_legacy_audio_pages_redirect_to_tools(self) -> None:
        from transcriptx.web.navigation import migrate_legacy_page_key

        assert migrate_legacy_page_key("Audio Prep") == ("Tools", "Preprocessing")
        assert migrate_legacy_page_key("Audio Merge") == ("Tools", "Merge")


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


class TestSerialGroupHideRestore:
    def test_hide_and_restore_round_trip(self) -> None:
        session: dict = {}
        key = "numeric_index:260223_team_facilitation"
        hide_serial_group_in_session(session, key)
        hide_serial_group_in_session(session, key)
        assert hidden_serial_keys_from_session(session) == [key]
        restore_serial_group_in_session(session, key)
        assert hidden_serial_keys_from_session(session) == []

    def test_merge_panel_has_hide_and_restore_controls(self) -> None:
        import transcriptx.web.ui.tools.merge_panel as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert '"Hide"' in source
        assert "audio_merge_hide_group_" in source
        assert "Hidden suggestions" in source
        assert "audio_merge_restore_group_" in source


class TestPageIntegrationPresence:
    def test_transcribe_audio_is_external_instructions(self) -> None:
        import transcriptx.web.page_modules.transcribe_audio as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "whispermlx-missing" in source
        assert "Import Transcript" in source
        assert "consume_transcription_nav_paths" in source

    def test_serial_group_prompt_points_at_tools_merge(self) -> None:
        import transcriptx.web.components.serial_group_prompt as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "render_serial_group_prompt" in source
        assert "Workflow → Audio Preprocessing → Merge" in source
        assert "Transcribe these files separately anyway" in source
        assert "Open Audio Preprocessing → Merge" in source
