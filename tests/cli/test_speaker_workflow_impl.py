"""
Tests for speaker identification workflow implementation.
"""

from unittest.mock import patch

from transcriptx.cli.speaker_workflow import run_speaker_identification_workflow


class TestSpeakerWorkflowImpl:
    """Tests for speaker identification workflow."""

    def test_speaker_workflow_complete(self, tmp_path):
        transcript_path = tmp_path / "test.json"
        transcript_path.write_text(
            '{"segments": [{"speaker": "SPEAKER_00", "text": "Hello"}]}'
        )

        with (
            patch(
                "transcriptx.cli.speaker_workflow.select_folder_interactive"
            ) as mock_select_folder,
            patch("transcriptx.cli.speaker_workflow.questionary.select") as mock_select,
            patch(
                "transcriptx.cli.speaker_workflow.load_segments"
            ) as mock_load_segments,
            patch(
                "transcriptx.cli.speaker_workflow.build_speaker_map"
            ) as mock_build_map,
            patch(
                "transcriptx.cli.speaker_workflow.rename_transcript_after_speaker_mapping"
            ) as mock_rename,
            patch(
                "transcriptx.cli.speaker_workflow.get_current_transcript_path_from_state"
            ) as mock_current_path,
            patch(
                "transcriptx.cli.speaker_workflow.store_transcript_after_speaker_identification"
            ) as mock_store,
        ):

            mock_select_folder.return_value = tmp_path
            mock_select.return_value.ask.return_value = f"✨ {transcript_path.name}"
            mock_load_segments.return_value = [
                {"speaker": "SPEAKER_00", "text": "Hello"}
            ]
            mock_build_map.return_value = {"SPEAKER_00": "Alice"}
            mock_current_path.return_value = str(transcript_path)

            run_speaker_identification_workflow()

            mock_build_map.assert_called_once()
            mock_rename.assert_called_once()
            mock_store.assert_called_once_with(str(transcript_path))

    def test_speaker_workflow_no_folder_selected(self):
        with patch(
            "transcriptx.cli.speaker_workflow.select_folder_interactive"
        ) as mock_select_folder:
            mock_select_folder.return_value = None

            run_speaker_identification_workflow()

            mock_select_folder.assert_called_once()

    def test_speaker_workflow_user_cancels_mapping(self, tmp_path):
        transcript_path = tmp_path / "test.json"
        transcript_path.write_text(
            '{"segments": [{"speaker": "SPEAKER_00", "text": "Hello"}]}'
        )

        with (
            patch(
                "transcriptx.cli.speaker_workflow.select_folder_interactive"
            ) as mock_select_folder,
            patch("transcriptx.cli.speaker_workflow.questionary.select") as mock_select,
            patch(
                "transcriptx.cli.speaker_workflow.load_segments"
            ) as mock_load_segments,
            patch(
                "transcriptx.cli.speaker_workflow.build_speaker_map"
            ) as mock_build_map,
            patch(
                "transcriptx.cli.speaker_workflow.rename_transcript_after_speaker_mapping"
            ) as mock_rename,
            patch(
                "transcriptx.cli.speaker_workflow.store_transcript_after_speaker_identification"
            ) as mock_store,
        ):

            mock_select_folder.return_value = tmp_path
            mock_select.return_value.ask.return_value = f"✨ {transcript_path.name}"
            mock_load_segments.return_value = [
                {"speaker": "SPEAKER_00", "text": "Hello"}
            ]
            mock_build_map.return_value = None

            run_speaker_identification_workflow()

            mock_build_map.assert_called_once()
            mock_rename.assert_not_called()
            mock_store.assert_not_called()
