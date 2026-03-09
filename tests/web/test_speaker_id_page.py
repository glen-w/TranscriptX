"""
Tests for the Speaker Identification page module (web/page_modules/speaker_id.py).

Contract: page imports only SpeakerStudioController (not lower-level services).
Integration: speaker-by-speaker naming flow via the controller.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.services.speaker_studio.controller import SpeakerStudioController


# ── contract ──────────────────────────────────────────────────────────────────


def test_speaker_id_page_imports_only_controller() -> None:
    """Contract: speaker_id page must not import SegmentIndexService, ClipService, or SpeakerMappingService."""
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text()
    assert "SpeakerStudioController" in source
    assert "SegmentIndexService" not in source
    assert "ClipService" not in source
    assert "SpeakerMappingService" not in source


def test_speaker_id_page_exposes_render_function() -> None:
    """Contract: render_speaker_id_page must be importable and callable."""
    from transcriptx.web.page_modules.speaker_id import render_speaker_id_page

    assert callable(render_speaker_id_page)


# ── helper fixtures ───────────────────────────────────────────────────────────


def _make_transcript(path: Path, speakers: list[dict]) -> None:
    """Write a minimal transcript JSON with given segments."""
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "speaker_map": {},
                "ignored_speakers": [],
                "segments": speakers,
            }
        )
    )


@pytest.fixture()
def transcript_dir(tmp_path: Path) -> Path:
    (tmp_path / "transcripts").mkdir()
    return tmp_path


@pytest.fixture()
def two_speaker_transcript(transcript_dir: Path) -> Path:
    path = transcript_dir / "transcripts" / "meeting_transcriptx.json"
    _make_transcript(
        path,
        [
            {
                "start": 0.0,
                "end": 2.5,
                "speaker": "SPEAKER_00",
                "text": "Good morning everyone.",
            },
            {
                "start": 2.5,
                "end": 5.0,
                "speaker": "SPEAKER_01",
                "text": "Hi, thanks for joining.",
            },
            {
                "start": 5.0,
                "end": 8.0,
                "speaker": "SPEAKER_00",
                "text": "Let us get started.",
            },
            {
                "start": 8.0,
                "end": 10.0,
                "speaker": "SPEAKER_01",
                "text": "Sounds good.",
            },
        ],
    )
    return path


# ── integration ───────────────────────────────────────────────────────────────


def test_speaker_id_initial_state_is_none(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """Fresh transcript starts with speaker_map_status='none'."""
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(transcript_dir))
    import transcriptx.core.utils.paths as paths_mod

    monkeypatch.setattr(paths_mod, "DATA_DIR", str(transcript_dir))

    controller = SpeakerStudioController(data_dir=transcript_dir)
    transcripts = controller.list_transcripts(data_dir=transcript_dir)
    assert len(transcripts) == 1
    assert transcripts[0].speaker_map_status == "none"
    assert transcripts[0].unique_speaker_count == 2


def test_speaker_id_segments_grouped_by_diarized_id(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """list_segments returns all segments; helper groups them by diarized ID correctly."""
    from transcriptx.web.page_modules.speaker_id import _group_by_diarized_id

    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(transcript_dir))
    import transcriptx.core.utils.paths as paths_mod

    monkeypatch.setattr(paths_mod, "DATA_DIR", str(transcript_dir))

    controller = SpeakerStudioController(data_dir=transcript_dir)
    segments = controller.list_segments(str(two_speaker_transcript))
    assert len(segments) == 4

    groups = _group_by_diarized_id(segments)
    assert set(groups.keys()) == {"SPEAKER_00", "SPEAKER_01"}
    assert len(groups["SPEAKER_00"]) == 2
    assert len(groups["SPEAKER_01"]) == 2


def test_speaker_id_assign_name_reflected_in_mapping(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """Assigning a name via apply_mapping_mutation updates the transcript JSON."""
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(transcript_dir))
    import transcriptx.core.utils.paths as paths_mod

    monkeypatch.setattr(paths_mod, "DATA_DIR", str(transcript_dir))

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.apply_mapping_mutation(
        str(two_speaker_transcript), "SPEAKER_00", "Alice", method="web"
    )

    state = controller.get_mapping_status(str(two_speaker_transcript))
    assert state.speaker_map.get("SPEAKER_00") == "Alice"
    assert state.speaker_map.get("SPEAKER_01") in (None, "")

    data = json.loads(two_speaker_transcript.read_text())
    alice_segs = [s for s in data["segments"] if s["speaker"] == "Alice"]
    assert len(alice_segs) == 2


def test_speaker_id_ignore_speaker(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """ignore_speaker marks the diarized ID as ignored."""
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(transcript_dir))
    import transcriptx.core.utils.paths as paths_mod

    monkeypatch.setattr(paths_mod, "DATA_DIR", str(transcript_dir))

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.ignore_speaker(str(two_speaker_transcript), "SPEAKER_01", method="web")

    state = controller.get_mapping_status(str(two_speaker_transcript))
    assert "SPEAKER_01" in state.ignored_speakers


def test_speaker_id_unignore_speaker(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """unignore_speaker removes the diarized ID from the ignored list."""
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(transcript_dir))
    import transcriptx.core.utils.paths as paths_mod

    monkeypatch.setattr(paths_mod, "DATA_DIR", str(transcript_dir))

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.ignore_speaker(str(two_speaker_transcript), "SPEAKER_01", method="web")
    controller.unignore_speaker(str(two_speaker_transcript), "SPEAKER_01", method="web")

    state = controller.get_mapping_status(str(two_speaker_transcript))
    assert "SPEAKER_01" not in state.ignored_speakers


def test_speaker_id_full_flow_both_speakers_named(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """Naming all speakers results in speaker_map_status='complete'."""
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(transcript_dir))
    import transcriptx.core.utils.paths as paths_mod

    monkeypatch.setattr(paths_mod, "DATA_DIR", str(transcript_dir))

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.apply_mapping_mutation(
        str(two_speaker_transcript), "SPEAKER_00", "Alice", method="web"
    )
    controller.apply_mapping_mutation(
        str(two_speaker_transcript), "SPEAKER_01", "Bob", method="web"
    )

    transcripts = controller.list_transcripts(data_dir=transcript_dir)
    assert transcripts[0].speaker_map_status == "complete"


def test_speaker_id_fmt_time_helper() -> None:
    """_fmt_time formats seconds into M:SS and H:MM:SS correctly."""
    from transcriptx.web.page_modules.speaker_id import _fmt_time

    assert _fmt_time(0.0) == "0:00"
    assert _fmt_time(59.9) == "0:59"
    assert _fmt_time(60.0) == "1:00"
    assert _fmt_time(3661.0) == "1:01:01"


def test_speaker_id_next_unnamed_idx_skips_named_and_ignored() -> None:
    """_next_unnamed_idx advances past already-named or ignored speakers."""
    from transcriptx.web.page_modules.speaker_id import _next_unnamed_idx

    speaker_ids = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03"]
    speaker_map = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
    ignored = ["SPEAKER_02"]

    # From index 0, should find SPEAKER_03 (index 3) as the next unnamed, non-ignored
    result = _next_unnamed_idx(speaker_ids, speaker_map, ignored, current=0)
    assert result == 3


def test_speaker_id_next_unnamed_idx_wraps_around() -> None:
    """_next_unnamed_idx wraps from end to beginning when nothing unnamed is after current."""
    from transcriptx.web.page_modules.speaker_id import _next_unnamed_idx

    speaker_ids = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
    speaker_map = {"SPEAKER_01": "Bob", "SPEAKER_02": "Carol"}
    ignored: list[str] = []

    # From index 2 (Carol), wrap around to find SPEAKER_00 (index 0)
    result = _next_unnamed_idx(speaker_ids, speaker_map, ignored, current=2)
    assert result == 0


def test_speaker_id_next_unnamed_idx_stays_when_all_named() -> None:
    """_next_unnamed_idx returns current when every speaker is named or ignored."""
    from transcriptx.web.page_modules.speaker_id import _next_unnamed_idx

    speaker_ids = ["SPEAKER_00", "SPEAKER_01"]
    speaker_map = {"SPEAKER_00": "Alice", "SPEAKER_01": "Bob"}
    ignored: list[str] = []

    result = _next_unnamed_idx(speaker_ids, speaker_map, ignored, current=0)
    assert result == 0
