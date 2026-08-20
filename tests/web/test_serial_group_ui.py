"""Tests for serial group UI helpers and Tools merge navigation."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.web.streamlit_doubles import DummyColumn, DummyHomeStreamlit
from transcriptx.core.audio.serial_groups import SerialGroup, detect_serial_audio_groups
from transcriptx.web.navigation import (
    MERGE_ORDERED_PATHS_KEY,
    TOOLS_HUB_FORCE_TAB_KEY,
    TOOLS_HUB_TAB_KEY,
    TRANSCRIPTION_NAV_PATHS_KEY,
    consume_transcription_nav_paths,
    navigate_to_tools_tab,
    navigate_to_transcribe_with_paths,
    normalize_tools_hub_tab,
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
        assert migrate_legacy_page_key("Audio Merge") == ("Tools", "Auto-merge")

    def test_normalize_tools_hub_tab_aliases(self) -> None:
        assert normalize_tools_hub_tab(None) == "Preprocessing"
        assert normalize_tools_hub_tab("") == "Preprocessing"
        assert normalize_tools_hub_tab("Merge") == "Auto-merge"
        assert normalize_tools_hub_tab("Auto-merge") == "Auto-merge"
        assert normalize_tools_hub_tab("Manual merge") == "Manual merge"
        assert normalize_tools_hub_tab("Preprocessing") == "Preprocessing"
        assert normalize_tools_hub_tab("Unknown Tab") == "Preprocessing"

    def test_navigate_to_tools_tab_merge_alias_sets_ordered_paths(self) -> None:
        session: dict = {}
        navigate_to_tools_tab(
            session,
            "Merge",
            merge_ordered_paths=[Path("/tmp/a.wav"), Path("/tmp/b.wav")],
        )
        assert session["page"] == "Tools"
        assert session[TOOLS_HUB_TAB_KEY] == "Auto-merge"
        assert session[TOOLS_HUB_FORCE_TAB_KEY] == "Auto-merge"
        assert session[MERGE_ORDERED_PATHS_KEY] == ["/tmp/a.wav", "/tmp/b.wav"]


class TestSerialGroupPrompt:
    def test_format_duration_edges(self) -> None:
        from transcriptx.web.components.serial_group_prompt import _format_duration

        assert _format_duration(None) == "—"
        assert _format_duration(-1) == "—"
        assert _format_duration(0) == "0s"
        assert _format_duration(45) == "45s"
        assert _format_duration(125) == "2m 5s"
        assert _format_duration(3661) == "1h 1m 1s"

    @pytest.mark.unit
    def test_render_serial_group_prompt_returns_state(self, monkeypatch) -> None:
        import transcriptx.web.components.serial_group_prompt as mod

        warnings: list[str] = []
        captions: list[str] = []
        texts: list[str] = []
        button_labels: list[str] = []
        DummyHomeStreamlit.session_state = {}

        class _St(DummyHomeStreamlit):
            @staticmethod
            def warning(msg, **_k):
                warnings.append(str(msg))

            @staticmethod
            def caption(msg, **_k):
                captions.append(str(msg))

            @staticmethod
            def text(msg, **_k):
                texts.append(str(msg))

            @staticmethod
            def columns(n, **_kwargs):
                return tuple(DummyColumn() for _ in range(n))

            @staticmethod
            def button(label, **_k):
                button_labels.append(str(label))
                return label.startswith("Merge")

            @staticmethod
            def checkbox(_label, *, value=False, key=None, **_k):
                if key is not None:
                    DummyHomeStreamlit.session_state[key] = True
                return True

        group = SerialGroup(
            base_key="meeting",
            ordered_paths=(Path("/rec/meeting_1.wav"), Path("/rec/meeting_2.wav")),
            confidence="high",
            matched_rule="timestamp_suffix",
            warnings=("gap between parts",),
        )
        durations = {
            Path("/rec/meeting_1.wav"): 30.0,
            Path("/rec/meeting_2.wav"): 45.0,
        }

        monkeypatch.setattr(mod, "st", _St)
        state = mod.render_serial_group_prompt(
            [group],
            separate_ok_key="sep_ok",
            merge_button_key="merge_btn",
            review_button_key="review_btn",
            duration_lookup=durations.get,
        )

        assert any("Auto-merge" in w for w in warnings)
        assert any("Combined duration" in c and "1m 15s" in c for c in captions)
        assert any("gap between parts" in c for c in captions)
        assert any("meeting_1.wav" in t for t in texts)
        assert "Merge detected groups and transcribe" in button_labels
        assert "Open Audio Preprocessing → Auto-merge" in button_labels
        assert state.merge_and_transcribe_clicked is True
        assert state.review_in_merge_clicked is False
        assert state.transcribe_separately_ok is True


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

    def test_merge_panel_previews_files_in_detected_groups(self) -> None:
        import transcriptx.web.ui.tools.merge_panel as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        assert "_render_merge_file_preview" in source
        assert "audio_merge_preview_" in source
        # Streamlit MediaMixin.audio has no `key`; identity lives on the container.
        assert "st.audio(path.read_bytes(), key=" not in source
        assert 'st.container(key=f"audio_merge_preview_{key_suffix}")' in source


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
        assert "Workflow → Audio Preprocessing → Auto-merge" in source
        assert "Transcribe these files separately anyway" in source
        assert "Open Audio Preprocessing → Auto-merge" in source
