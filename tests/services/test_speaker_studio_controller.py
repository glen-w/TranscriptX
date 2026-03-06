"""Unit tests for SpeakerStudioController: delegation to SegmentIndex, ClipService, MappingService."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


from transcriptx.services.speaker_studio.controller import SpeakerStudioController
from transcriptx.services.speaker_studio.segment_index import (
    TranscriptSummary,
    SegmentInfo,
)
from transcriptx.services.speaker_studio.mapping_service import SpeakerMapState


def test_controller_list_transcripts_delegates_to_segment_index(tmp_path: Path) -> None:
    (tmp_path / "transcripts").mkdir()
    with patch(
        "transcriptx.services.speaker_studio.controller.SegmentIndexService"
    ) as SegIdx:
        mock_svc = MagicMock()
        mock_svc.list_transcripts.return_value = [
            TranscriptSummary(
                path=str(tmp_path / "transcripts" / "a.json"),
                base_name="a",
                speaker_map_status="none",
                segment_count=2,
                unique_speaker_count=1,
            ),
        ]
        SegIdx.return_value = mock_svc
        ctrl = SpeakerStudioController(data_dir=tmp_path)
        out = ctrl.list_transcripts(data_dir=tmp_path)
        assert len(out) == 1
        assert out[0].base_name == "a"
        mock_svc.list_transcripts.assert_called_once_with(
            data_dir=tmp_path, canonical_only=False
        )


def test_controller_list_segments_delegates(tmp_path: Path) -> None:
    with patch(
        "transcriptx.services.speaker_studio.controller.SegmentIndexService"
    ) as SegIdx:
        mock_svc = MagicMock()
        mock_svc.list_segments.return_value = [
            SegmentInfo(
                index=0,
                start=0.0,
                end=1.0,
                text="Hi",
                speaker="SPEAKER_00",
                speaker_diarized_id="SPEAKER_00",
            ),
        ]
        SegIdx.return_value = mock_svc
        ctrl = SpeakerStudioController(data_dir=tmp_path)
        out = ctrl.list_segments("/path/to/t.json")
        assert len(out) == 1
        assert out[0].text == "Hi"
        mock_svc.list_segments.assert_called_once_with("/path/to/t.json")


def test_controller_apply_mapping_mutation_delegates(tmp_path: Path) -> None:
    with patch(
        "transcriptx.services.speaker_studio.controller.SpeakerMappingService"
    ) as MapSvc:
        mock_svc = MagicMock()
        mock_svc.assign_speaker.return_value = SpeakerMapState(
            speaker_map={"SPEAKER_00": "Alice"},
            ignored_speakers=[],
            schema_version="1.0",
            provenance={"method": "web"},
        )
        MapSvc.return_value = mock_svc
        ctrl = SpeakerStudioController(data_dir=tmp_path)
        state = ctrl.apply_mapping_mutation(
            "/path/to/t.json", "SPEAKER_00", "Alice", method="web"
        )
        assert state.speaker_map["SPEAKER_00"] == "Alice"
        mock_svc.assign_speaker.assert_called_once_with(
            "/path/to/t.json", "SPEAKER_00", "Alice", method="web"
        )


def test_controller_ignore_speaker_delegates(tmp_path: Path) -> None:
    with patch(
        "transcriptx.services.speaker_studio.controller.SpeakerMappingService"
    ) as MapSvc:
        mock_svc = MagicMock()
        mock_svc.ignore_speaker.return_value = SpeakerMapState(
            speaker_map={},
            ignored_speakers=["SPEAKER_01"],
            schema_version="1.0",
            provenance=None,
        )
        MapSvc.return_value = mock_svc
        ctrl = SpeakerStudioController(data_dir=tmp_path)
        state = ctrl.ignore_speaker("/path/to/t.json", "SPEAKER_01", method="web")
        assert "SPEAKER_01" in state.ignored_speakers
        mock_svc.ignore_speaker.assert_called_once_with(
            "/path/to/t.json", "SPEAKER_01", method="web"
        )


def test_controller_get_mapping_status_delegates(tmp_path: Path) -> None:
    with patch(
        "transcriptx.services.speaker_studio.controller.SpeakerMappingService"
    ) as MapSvc:
        mock_svc = MagicMock()
        mock_svc.get_mapping.return_value = SpeakerMapState(
            speaker_map={"SPEAKER_00": "Alice"},
            ignored_speakers=[],
            schema_version="1.0",
            provenance=None,
        )
        MapSvc.return_value = mock_svc
        ctrl = SpeakerStudioController(data_dir=tmp_path)
        state = ctrl.get_mapping_status("/path/to/t.json")
        assert state.speaker_map["SPEAKER_00"] == "Alice"
        mock_svc.get_mapping.assert_called_once_with("/path/to/t.json")
