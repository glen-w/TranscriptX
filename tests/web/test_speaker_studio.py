"""
Integration tests for Speaker Studio: page imports only controller; assign speaker flow.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.services.speaker_studio.controller import SpeakerStudioController


def test_speaker_studio_page_imports_only_controller() -> None:
    """Contract: Speaker Studio page module must not import SegmentIndexService, ClipService, SpeakerMappingService."""
    import transcriptx.web.page_modules.speaker_studio as mod

    source = Path(mod.__file__).read_text()
    assert "SpeakerStudioController" in source
    assert "SegmentIndexService" not in source
    assert "ClipService" not in source
    assert "SpeakerMappingService" not in source


def test_studio_controller_list_and_assign_speaker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With a fixture transcript, list transcripts, list segments, assign speaker, get_mapping_status reflects it."""
    (tmp_path / "transcripts").mkdir()
    transcript_path = tmp_path / "transcripts" / "meeting_transcriptx.json"
    transcript_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "segments": [
                    {
                        "start": 0.0,
                        "end": 2.0,
                        "speaker": "SPEAKER_00",
                        "text": "Hello",
                    },
                    {
                        "start": 2.0,
                        "end": 4.0,
                        "speaker": "SPEAKER_01",
                        "text": "Hi there",
                    },
                ],
            }
        )
    )
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(tmp_path))
    # Ensure path resolution sees our dir
    import transcriptx.core.utils.paths as paths_mod

    monkeypatch.setattr(paths_mod, "DATA_DIR", str(tmp_path))

    controller = SpeakerStudioController(data_dir=tmp_path)
    transcripts = controller.list_transcripts(data_dir=tmp_path)
    assert len(transcripts) == 1
    assert "meeting" in transcripts[0].base_name
    assert transcripts[0].speaker_map_status == "none"

    segments = controller.list_segments(str(transcript_path))
    assert len(segments) == 2
    assert segments[0].speaker == "SPEAKER_00"

    state_before = controller.get_mapping_status(str(transcript_path))
    assert (
        state_before.speaker_map.get("SPEAKER_00") is None
        or state_before.speaker_map.get("SPEAKER_00") == ""
    )

    controller.apply_mapping_mutation(
        str(transcript_path), "SPEAKER_00", "Alice", method="web"
    )

    state_after = controller.get_mapping_status(str(transcript_path))
    assert state_after.speaker_map.get("SPEAKER_00") == "Alice"

    data = json.loads(transcript_path.read_text())
    assert data["segments"][0]["speaker"] == "Alice"
    assert "speaker_map_provenance" in data or "speaker_map_schema_version" in data
