"""G1 transcript stitch: identity-safe concatenate."""

from __future__ import annotations

import pytest

from transcriptx.io.transcript_stitch import (
    TranscriptStitchError,
    stitch_transcript_documents,
    write_stitched_transcript,
)


def _doc(segments, duration):
    return {
        "schema_version": 1,
        "metadata": {"duration": duration, "language": "en"},
        "segments": segments,
    }


def test_rebase_and_concat() -> None:
    a = _doc([{"speaker": "SPEAKER_00", "start": 0.0, "end": 2.0, "text": "hi"}], 2.0)
    b = _doc(
        [{"speaker": "SPEAKER_00", "start": 0.0, "end": 1.0, "text": "there"}], 1.0
    )
    out = stitch_transcript_documents([a, b], source_stems=["a", "b"])
    assert len(out["segments"]) == 2
    assert out["segments"][1]["start"] == 2.0
    assert out["segments"][1]["end"] == 3.0
    assert out["segments"][0]["speaker"] == "SPEAKER_00"
    assert out["stitch"]["part_count"] == 2


def test_duration_mismatch_aborts() -> None:
    a = _doc([{"speaker": "SPEAKER_00", "start": 0.0, "end": 1.0, "text": "x"}], 40.0)
    b = _doc([{"speaker": "SPEAKER_00", "start": 0.0, "end": 1.0, "text": "y"}], 1.0)
    with pytest.raises(TranscriptStitchError, match="cannot be reconciled"):
        stitch_transcript_documents([a, b])


def test_refuses_overwrite(tmp_path) -> None:
    dest = tmp_path / "out.json"
    dest.write_text("{}", encoding="utf-8")
    with pytest.raises(TranscriptStitchError, match="overwrite"):
        write_stitched_transcript(dest, {"segments": []})
