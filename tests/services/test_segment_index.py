"""Unit tests for SegmentIndexService (completeness status)."""

from __future__ import annotations

import json


from transcriptx.services.speaker_studio import SegmentIndexService


def test_completeness_none(tmp_path) -> None:
    """No speaker_map and no ignored_speakers -> none."""
    (tmp_path / "transcripts").mkdir()
    p = tmp_path / "transcripts" / "t_transcriptx.json"
    p.write_text(json.dumps({"segments": [{"speaker": "SPEAKER_00", "text": "Hi"}]}))
    svc = SegmentIndexService(tmp_path)
    summaries = svc.list_transcripts()
    assert len(summaries) == 1
    assert summaries[0].speaker_map_status == "none"


def test_completeness_partial(tmp_path) -> None:
    """Some diarized IDs mapped, one not -> partial."""
    (tmp_path / "transcripts").mkdir()
    p = tmp_path / "transcripts" / "t_transcriptx.json"
    p.write_text(
        json.dumps(
            {
                "segments": [
                    {"speaker": "SPEAKER_00", "text": "A"},
                    {"speaker": "SPEAKER_01", "text": "B"},
                ],
                "speaker_map": {"SPEAKER_00": "Alice"},
            }
        )
    )
    svc = SegmentIndexService(tmp_path)
    summaries = svc.list_transcripts()
    assert len(summaries) == 1
    assert summaries[0].speaker_map_status == "partial"


def test_completeness_complete(tmp_path) -> None:
    """All diarized IDs in speaker_map or ignored -> complete."""
    (tmp_path / "transcripts").mkdir()
    p = tmp_path / "transcripts" / "t_transcriptx.json"
    p.write_text(
        json.dumps(
            {
                "segments": [{"speaker": "SPEAKER_00", "text": "A"}],
                "speaker_map": {"SPEAKER_00": "Alice"},
            }
        )
    )
    svc = SegmentIndexService(tmp_path)
    summaries = svc.list_transcripts()
    assert len(summaries) == 1
    assert summaries[0].speaker_map_status == "complete"
