"""SpeakerIdentifyService apply knobs (no SpeechBrain)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from transcriptx.core.speaker_profiles.identify.models import ChannelCandidate
from transcriptx.core.speaker_profiles.identify.service import SpeakerIdentifyService
from transcriptx.core.speaker_profiles.provenance import LinkProvenanceV1


@pytest.fixture
def transcript(tmp_path: Path) -> Path:
    path = tmp_path / "talk.json"
    path.write_text(
        json.dumps(
            {
                "segments": [
                    {"speaker": "SPEAKER_00", "text": "Hi everyone, I'm Maya."},
                    {
                        "speaker": "SPEAKER_01",
                        "text": "Thanks Maya, this is Jordan speaking.",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.unit
def test_auto_name_from_mentions(transcript: Path, tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    result = SpeakerIdentifyService(root=root).identify_transcript(
        transcript, auto_name=True, auto_link=False
    )
    assert result.error is None
    assert result.named_count >= 1
    from transcriptx.services.speaker_studio.mapping_service import SpeakerMappingService

    state = SpeakerMappingService().get_mapping(str(transcript))
    assert state.provenance is not None
    assert state.provenance.get("method") == "auto_identified"
    assert "Maya" in state.speaker_map.values()


@pytest.mark.unit
def test_does_not_overwrite_existing_name(transcript: Path, tmp_path: Path) -> None:
    from transcriptx.services.speaker_studio.mapping_service import SpeakerMappingService

    SpeakerMappingService().assign_speaker(
        str(transcript), "SPEAKER_00", "HumanName", method="web"
    )
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    SpeakerIdentifyService(root=root).identify_transcript(
        transcript, auto_name=True, auto_link=False
    )
    state = SpeakerMappingService().get_mapping(str(transcript))
    assert state.speaker_map["SPEAKER_00"] == "HumanName"


@pytest.mark.unit
def test_auto_link_off_skips_profile(transcript: Path, tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    match = MagicMock()
    match.analyse_occurrence.return_value = MagicMock(
        outcome="SuggestionAvailable",
        candidates_ui=(
            {
                "profile_id": "p-maya",
                "display_name": "Maya",
                "confidence": "strong",
                "score_diagnostic": 0.91,
            },
        ),
        suggestion_id="s1",
        suggestion_digest="digest",
        model_generation_id="gen1",
    )
    result = SpeakerIdentifyService(root=root, match_service=match).identify_transcript(
        transcript, auto_name=True, auto_link=False
    )
    linked = [row for row in result.applied if row.linked]
    assert linked == []


@pytest.mark.unit
def test_auto_identified_provenance_model() -> None:
    prov = LinkProvenanceV1(link_method="auto_identified", confidence_category="strong")
    assert prov.to_storage_dict()["link_method"] == "auto_identified"


@pytest.mark.unit
def test_dry_run_does_not_write_map(transcript: Path, tmp_path: Path) -> None:
    root = tmp_path / "speaker_profiles"
    root.mkdir()
    SpeakerIdentifyService(root=root).identify_transcript(
        transcript, auto_name=True, auto_link=False, dry_run=True
    )
    from transcriptx.services.speaker_studio.mapping_service import SpeakerMappingService

    state = SpeakerMappingService().get_mapping(str(transcript))
    assert not state.has_named_speakers or state.named_speaker_count == 0
