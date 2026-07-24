"""Unit tests for SegmentIndexService (completeness status)."""

from __future__ import annotations

import json

from transcriptx.services.speaker_studio import SegmentIndexService
from transcriptx.io.speaker_map_resolver import sidecar_path_for


def _v1(segments: list) -> dict:
    return {
        "schema_version": 1,
        "source": {
            "type": "manual",
            "original_path": "t.json",
            "imported_at": "2026-01-01T00:00:00Z",
        },
        "segments": segments,
    }


def test_completeness_none(tmp_path) -> None:
    """No speaker_map and no ignored_speakers -> none."""
    (tmp_path / "transcripts").mkdir()
    p = tmp_path / "transcripts" / "t_transcriptx.json"
    p.write_text(
        json.dumps(
            _v1(
                [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "Hi",
                        "start": 0.0,
                        "end": 1.0,
                    }
                ]
            )
        )
    )
    svc = SegmentIndexService(tmp_path)
    summaries = svc.list_transcripts()
    assert len(summaries) == 1
    assert summaries[0].speaker_map_status == "none"
    assert summaries[0].unidentified_speaker_count == 1
    assert summaries[0].ignored_speaker_count == 0


def test_completeness_partial(tmp_path) -> None:
    """Some diarized IDs mapped, one not -> partial."""
    (tmp_path / "transcripts").mkdir()
    p = tmp_path / "transcripts" / "t_transcriptx.json"
    p.write_text(
        json.dumps(
            _v1(
                [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "A",
                        "start": 0.0,
                        "end": 1.0,
                    },
                    {
                        "speaker": "SPEAKER_01",
                        "text": "B",
                        "start": 1.0,
                        "end": 2.0,
                    },
                ]
            )
        )
    )
    sidecar_path_for(p).write_text(
        json.dumps(
            {
                "speaker_map": {"SPEAKER_00": "Alice"},
                "ignored_speakers": [],
                "speaker_id_to_db_id": {},
                "speaker_map_schema_version": 1,
            }
        )
    )
    svc = SegmentIndexService(tmp_path)
    summaries = svc.list_transcripts()
    assert len(summaries) == 1
    assert summaries[0].speaker_map_status == "partial"
    assert summaries[0].unidentified_speaker_count == 1
    assert summaries[0].ignored_speaker_count == 0


def test_pick_counts_partial_with_ignored(tmp_path) -> None:
    """Partial map: counts reflect unnamed diarized IDs vs ignored."""
    (tmp_path / "transcripts").mkdir()
    p = tmp_path / "transcripts" / "t_transcriptx.json"
    p.write_text(
        json.dumps(
            _v1(
                [
                    {"speaker": "SPEAKER_00", "text": "A", "start": 0.0, "end": 1.0},
                    {"speaker": "SPEAKER_01", "text": "B", "start": 1.0, "end": 2.0},
                    {"speaker": "SPEAKER_02", "text": "C", "start": 2.0, "end": 3.0},
                ]
            )
        )
    )
    sidecar_path_for(p).write_text(
        json.dumps(
            {
                "speaker_map": {"SPEAKER_00": "Alice"},
                "ignored_speakers": ["SPEAKER_01"],
                "speaker_id_to_db_id": {},
                "speaker_map_schema_version": 1,
            }
        )
    )
    svc = SegmentIndexService(tmp_path)
    summaries = svc.list_transcripts()
    assert len(summaries) == 1
    assert summaries[0].speaker_map_status == "partial"
    assert summaries[0].unidentified_speaker_count == 1
    assert summaries[0].ignored_speaker_count == 1


def test_completeness_complete_when_segment_uses_variant_diarized_id(tmp_path) -> None:
    """SPEAKER_1 in segments matches SPEAKER_01 in sidecar (normalized keys)."""
    (tmp_path / "transcripts").mkdir()
    p = tmp_path / "transcripts" / "t_transcriptx.json"
    p.write_text(
        json.dumps(
            _v1(
                [
                    {"speaker": "SPEAKER_1", "text": "A", "start": 0.0, "end": 1.0},
                    {"speaker": "SPEAKER_2", "text": "B", "start": 1.0, "end": 2.0},
                ]
            )
        )
    )
    sidecar_path_for(p).write_text(
        json.dumps(
            {
                "speaker_map": {"SPEAKER_01": "Alice", "SPEAKER_02": "Bob"},
                "ignored_speakers": [],
                "speaker_id_to_db_id": {},
                "speaker_map_schema_version": 1,
            }
        )
    )
    svc = SegmentIndexService(tmp_path)
    summaries = svc.list_transcripts()
    assert len(summaries) == 1
    assert summaries[0].speaker_map_status == "complete"
    assert summaries[0].unidentified_speaker_count == 0
    assert summaries[0].ignored_speaker_count == 0


def test_pick_counts_complete_with_ignored_only(tmp_path) -> None:
    """All diarized IDs resolved via map or ignored: complete but ignored > 0."""
    (tmp_path / "transcripts").mkdir()
    p = tmp_path / "transcripts" / "t_transcriptx.json"
    p.write_text(
        json.dumps(
            _v1(
                [
                    {"speaker": "SPEAKER_00", "text": "A", "start": 0.0, "end": 1.0},
                    {"speaker": "SPEAKER_01", "text": "B", "start": 1.0, "end": 2.0},
                ]
            )
        )
    )
    sidecar_path_for(p).write_text(
        json.dumps(
            {
                "speaker_map": {"SPEAKER_00": "Alice"},
                "ignored_speakers": ["SPEAKER_01"],
                "speaker_id_to_db_id": {},
                "speaker_map_schema_version": 1,
            }
        )
    )
    svc = SegmentIndexService(tmp_path)
    summaries = svc.list_transcripts()
    assert len(summaries) == 1
    assert summaries[0].speaker_map_status == "complete"
    assert summaries[0].unidentified_speaker_count == 0
    assert summaries[0].ignored_speaker_count == 1


def test_self_mapping_placeholder_counts_as_unidentified(tmp_path) -> None:
    """SPEAKER_xx -> SPEAKER_xx is not an assigned name for completeness/counts."""
    (tmp_path / "transcripts").mkdir()
    p = tmp_path / "transcripts" / "t_transcriptx.json"
    p.write_text(
        json.dumps(
            _v1(
                [
                    {"speaker": "SPEAKER_00", "text": "A", "start": 0.0, "end": 1.0},
                    {"speaker": "SPEAKER_01", "text": "B", "start": 1.0, "end": 2.0},
                ]
            )
        )
    )
    sidecar_path_for(p).write_text(
        json.dumps(
            {
                "speaker_map": {"SPEAKER_00": "SPEAKER_00"},
                "ignored_speakers": [],
                "speaker_id_to_db_id": {},
                "speaker_map_schema_version": 1,
            }
        )
    )
    svc = SegmentIndexService(tmp_path)
    summaries = svc.list_transcripts()
    assert len(summaries) == 1
    assert summaries[0].speaker_map_status == "partial"
    assert summaries[0].unidentified_speaker_count == 2
    assert summaries[0].ignored_speaker_count == 0


def test_completeness_complete(tmp_path) -> None:
    """All diarized IDs in speaker_map or ignored -> complete."""
    (tmp_path / "transcripts").mkdir()
    p = tmp_path / "transcripts" / "t_transcriptx.json"
    p.write_text(
        json.dumps(
            _v1(
                [
                    {
                        "speaker": "SPEAKER_00",
                        "text": "A",
                        "start": 0.0,
                        "end": 1.0,
                    },
                ]
            )
        )
    )
    sidecar_path_for(p).write_text(
        json.dumps(
            {
                "speaker_map": {"SPEAKER_00": "Alice"},
                "ignored_speakers": [],
                "speaker_id_to_db_id": {},
                "speaker_map_schema_version": 1,
            }
        )
    )
    svc = SegmentIndexService(tmp_path)
    summaries = svc.list_transcripts()
    assert len(summaries) == 1
    assert summaries[0].speaker_map_status == "complete"
