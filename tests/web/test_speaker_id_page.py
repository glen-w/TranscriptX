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
from transcriptx.io.speaker_map_resolver import sidecar_path_for

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


def test_speaker_id_page_renders_post_completion_action_links() -> None:
    """When all speakers are identified, show homepage-style next-step links."""
    import transcriptx.web.page_modules.speaker_id as mod

    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert "_render_post_speaker_id_actions" in source
    assert "All speakers identified!" in source
    assert "render_recent_run_actions" in source
    assert "SectionId.SPEAKER_ID_COMPLETE" in source
    assert "render_configured_actions" in source


def test_latest_run_summary_for_transcript_builds_run_when_outputs_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import datetime

    import transcriptx.web.page_modules.speaker_id as mod

    outputs = tmp_path / "outputs"
    run_dir = outputs / "slug-a" / "20260713_032900_abcdef12"
    run_dir.mkdir(parents=True)
    transcript = tmp_path / "meeting.json"
    transcript.write_text("{}")

    monkeypatch.setattr(mod, "OUTPUTS_DIR", outputs)
    monkeypatch.setattr(
        mod,
        "resolve_transcript_context",
        lambda *_a, **_k: type(
            "R", (), {"subject_id": "slug-a", "run_id": "20260713_032900_abcdef12"}
        )(),
    )

    summary = mod._latest_run_summary_for_transcript(transcript)
    assert summary is not None
    assert summary.run_id == "20260713_032900_abcdef12"
    assert summary.run_dir == run_dir
    assert isinstance(summary.created_at, datetime)


def test_render_post_speaker_id_actions_uses_recent_run_strip(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import transcriptx.web.page_modules.speaker_id as mod
    from transcriptx.app.models.results import RunSummary
    from datetime import datetime

    called: dict[str, object] = {}

    def _fake_actions(run, *, row_index=0, key_prefix="home_run", section=None):
        called["run"] = run
        called["key_prefix"] = key_prefix
        called["row_index"] = row_index
        called["section"] = section

    monkeypatch.setattr(mod, "render_recent_run_actions", _fake_actions)
    monkeypatch.setattr(
        mod,
        "_latest_run_summary_for_transcript",
        lambda _p: RunSummary(
            run_dir=tmp_path / "slug" / "run1",
            transcript_path=tmp_path / "t.json",
            run_id="run1",
            created_at=datetime(2026, 7, 13),
            selected_modules=[],
        ),
    )

    mod._render_post_speaker_id_actions(tmp_path / "t.json")
    assert called["key_prefix"] == "speaker_id_run"
    assert called["row_index"] == 0
    assert getattr(called["run"], "run_id") == "run1"


def test_speaker_id_transcript_label_partial_shows_counts() -> None:
    from transcriptx.web.page_modules.speaker_id import _speaker_id_transcript_label
    from transcriptx.services.speaker_studio.segment_index import TranscriptSummary

    t = TranscriptSummary(
        path="/x.json",
        base_name="meeting",
        speaker_map_status="partial",
        segment_count=100,
        unique_speaker_count=3,
        unidentified_speaker_count=2,
        ignored_speaker_count=1,
    )
    label = _speaker_id_transcript_label(t)
    assert label.startswith("meeting (partial, 100 segs)")
    assert "2 unidentified" in label
    assert "1 ignored" in label


def test_speaker_id_transcript_label_complete_omits_extra_counts() -> None:
    from transcriptx.web.page_modules.speaker_id import _speaker_id_transcript_label
    from transcriptx.services.speaker_studio.segment_index import TranscriptSummary

    t = TranscriptSummary(
        path="/x.json",
        base_name="meeting",
        speaker_map_status="complete",
        segment_count=50,
        unique_speaker_count=2,
        unidentified_speaker_count=0,
        ignored_speaker_count=1,
    )
    assert _speaker_id_transcript_label(t) == "meeting (complete, 50 segs)"


# ── helper fixtures ───────────────────────────────────────────────────────────


def _make_transcript(path: Path, speakers: list[dict]) -> None:
    """Write a minimal v1.0 transcript artifact with given segments."""
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "type": "manual",
                    "original_path": path.name,
                    "imported_at": "2026-01-01T00:00:00Z",
                },
                "segments": speakers,
            }
        )
    )


@pytest.fixture()
def transcript_dir(tmp_path: Path) -> Path:
    (tmp_path / "transcripts").mkdir()
    return tmp_path


def _configure_paths_for_transcripts_root(
    monkeypatch: pytest.MonkeyPatch, transcripts_root: Path
) -> None:
    """Point PATHS.transcripts_dir (and DATA_DIR) at a test-local transcripts root.

    This ensures canonical_transcript_relpath and speaker_map_path_for_transcript
    accept the test transcripts under tmp_path/transcripts.
    """
    import importlib
    import transcriptx.core.utils.paths as paths_mod

    # Ensure DATA_DIR and transcripts_dir env are consistent for PATHS rebuild.
    monkeypatch.setenv("TRANSCRIPTX_DATA_DIR", str(transcripts_root.parent))
    monkeypatch.setenv("TRANSCRIPTX_TRANSCRIPTS_DIR", str(transcripts_root))

    importlib.reload(paths_mod)


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
    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

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

    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

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
    """Assigning a name via apply_mapping_mutation updates the sidecar only."""
    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.apply_mapping_mutation(
        str(two_speaker_transcript), "SPEAKER_00", "Alice", method="web"
    )

    state = controller.get_mapping_status(str(two_speaker_transcript))
    assert state.speaker_map.get("SPEAKER_00") == "Alice"
    assert state.speaker_map.get("SPEAKER_01") in (None, "")

    data = json.loads(two_speaker_transcript.read_text())
    assert all(s["speaker"].startswith("SPEAKER_") for s in data["segments"])

    sidecar = json.loads(sidecar_path_for(two_speaker_transcript).read_text())
    assert sidecar["speaker_map"]["SPEAKER_00"] == "Alice"

    segments = controller.list_segments(str(two_speaker_transcript))
    alice_segs = [s for s in segments if s.speaker == "Alice"]
    assert len(alice_segs) == 2


def test_speaker_id_ignore_speaker(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
    two_speaker_transcript: Path,
) -> None:
    """ignore_speaker marks the diarized ID as ignored."""
    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

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
    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

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
    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

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


def test_speaker_id_next_unnamed_idx_after_save_moves_to_next_unnamed() -> None:
    """Saving current speaker should advance to the next unnamed speaker when present."""
    from transcriptx.web.page_modules.speaker_id import _next_unnamed_idx

    speaker_ids = ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02", "SPEAKER_03"]
    speaker_map = {
        "SPEAKER_00": "Alice",
        "SPEAKER_02": "Carol",
    }
    ignored: list[str] = []
    current_idx = 0  # active speaker is SPEAKER_00

    # Mirror the save-path behavior: current speaker is now named.
    map_after_save = speaker_map | {"SPEAKER_00": "Alice"}
    result = _next_unnamed_idx(
        speaker_ids,
        map_after_save,
        ignored,
        current=current_idx,
    )

    # SPEAKER_01 is the next unnamed speaker and should be selected.
    assert result == 1


def test_speaker_map_display_name_variant_id_matches_sidecar() -> None:
    """Sidecar keys are normalized; UI lookups must accept variant diarized ids."""
    from transcriptx.web.page_modules.speaker_id import _speaker_map_display_name

    m = {"SPEAKER_01": "Andrea", "SPEAKER_02": "Bob"}
    assert _speaker_map_display_name(m, "SPEAKER_1") == "Andrea"
    assert _speaker_map_display_name(m, "SPEAKER_01") == "Andrea"
    assert _speaker_map_display_name(m, "SPEAKER_2") == "Bob"


def test_speaker_map_display_name_ignores_placeholder_self_mapping() -> None:
    """Mappings like SPEAKER_00 -> SPEAKER_00 should still render as unnamed."""
    from transcriptx.web.page_modules.speaker_id import _speaker_map_display_name

    m = {"SPEAKER_00": "SPEAKER_00", "SPEAKER_01": "Alice"}
    assert _speaker_map_display_name(m, "SPEAKER_00") == ""
    assert _speaker_map_display_name(m, "SPEAKER_01") == "Alice"


def test_speaker_id_named_and_remaining_counts_with_variant_diarized_ids(
    monkeypatch: pytest.MonkeyPatch,
    transcript_dir: Path,
) -> None:
    """Progress metrics match sidecar after naming when transcript uses SPEAKER_1-style ids."""
    from transcriptx.web.page_modules.speaker_id import (
        _group_by_diarized_id,
        _is_speaker_ignored,
        _speaker_map_display_name,
    )

    path = transcript_dir / "transcripts" / "variant_ids_transcriptx.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "source": {
                    "type": "manual",
                    "original_path": path.name,
                    "imported_at": "2026-01-01T00:00:00Z",
                },
                "segments": [
                    {"start": 0.0, "end": 1.0, "speaker": "SPEAKER_1", "text": "A"},
                    {"start": 1.0, "end": 2.0, "speaker": "SPEAKER_2", "text": "B"},
                    {"start": 2.0, "end": 3.0, "speaker": "SPEAKER_3", "text": "C"},
                ],
            }
        )
    )

    _configure_paths_for_transcripts_root(monkeypatch, transcript_dir / "transcripts")

    controller = SpeakerStudioController(data_dir=transcript_dir)
    controller.apply_mapping_mutation(str(path), "SPEAKER_1", "Alice", method="web")
    controller.apply_mapping_mutation(str(path), "SPEAKER_2", "Bob", method="web")
    controller.ignore_speaker(str(path), "SPEAKER_3", method="web")

    state = controller.get_mapping_status(str(path))
    speaker_map = state.speaker_map or {}
    ignored = getattr(state, "ignored_speakers", None) or []

    segments = controller.list_segments(str(path))
    groups = _group_by_diarized_id(segments)
    speaker_ids = list(groups.keys())

    total = len(speaker_ids)
    named = sum(
        1
        for sid in speaker_ids
        if _speaker_map_display_name(speaker_map, sid)
        and not _is_speaker_ignored(ignored, sid)
    )
    n_ignored = sum(1 for sid in speaker_ids if _is_speaker_ignored(ignored, sid))
    remaining = total - named - n_ignored

    assert total == 3
    assert named == 2
    assert n_ignored == 1
    assert remaining == 0

    transcripts = controller.list_transcripts(data_dir=transcript_dir)
    assert transcripts[0].speaker_map_status == "complete"
