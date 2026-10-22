"""Tests for Granite / mlx-audio JSON → WhisperX converter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.services.transcription.granite_json_to_whisperx import (
    convert_file,
    segments_from_payload,
    speaker_label,
    stitch_chunk_payloads,
)


@pytest.mark.unit
def test_speaker_label_ibm_one_based() -> None:
    assert speaker_label(1) == "SPEAKER_00"
    assert speaker_label("Speaker 2") == "SPEAKER_01"
    assert speaker_label("SPEAKER_03") == "SPEAKER_03"


@pytest.mark.unit
def test_plain_text_uses_chunk_span() -> None:
    segs = segments_from_payload(
        {"text": "hello world"}, time_offset=10.0, duration=5.0
    )
    assert len(segs) == 1
    assert segs[0]["start"] == 10.0
    assert segs[0]["end"] == 15.0
    assert segs[0]["text"] == "hello world"
    assert "speaker" not in segs[0]


@pytest.mark.unit
def test_saa_segments_estimated_times() -> None:
    segs = segments_from_payload(
        {
            "segments": [
                {"speaker_id": 1, "text": "aa"},
                {"speaker_id": 2, "text": "bbbb"},
            ]
        },
        time_offset=0.0,
        duration=6.0,
    )
    assert [s["speaker"] for s in segs] == ["SPEAKER_00", "SPEAKER_01"]
    assert segs[0]["start"] == 0.0
    assert segs[0]["end"] == pytest.approx(2.0)
    assert segs[1]["end"] == pytest.approx(6.0)


@pytest.mark.unit
def test_speaker_tags_in_text() -> None:
    segs = segments_from_payload(
        {"text": "[Speaker 1]: Hello [Speaker 2]: Hi there"},
        time_offset=0.0,
        duration=4.0,
    )
    assert len(segs) == 2
    assert segs[0]["speaker"] == "SPEAKER_00"
    assert segs[1]["text"] == "Hi there"


@pytest.mark.unit
def test_word_times_offset() -> None:
    segs = segments_from_payload(
        {
            "segments": [
                {
                    "text": "hello",
                    "words": [{"word": "hello", "start": 0.2, "end": 0.8}],
                }
            ]
        },
        time_offset=100.0,
    )
    assert segs[0]["start"] == pytest.approx(100.2)
    assert segs[0]["end"] == pytest.approx(100.8)


@pytest.mark.unit
def test_stitch_chunks() -> None:
    segs = stitch_chunk_payloads(
        [
            ({"text": "one"}, 0.0, 2.0),
            ({"text": "two"}, 2.0, 2.0),
        ]
    )
    assert [s["text"] for s in segs] == ["one", "two"]
    assert segs[1]["start"] == pytest.approx(2.0)


@pytest.mark.unit
def test_convert_fixtures(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "fixtures" / "transcripts" / "granite"
    out = tmp_path / "plain.json"
    convert_file(root / "plain.json", out, time_offset=0.0, duration=3.0)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["segments"][0]["text"].startswith("Welcome")
    out2 = tmp_path / "saa.json"
    convert_file(root / "saa.json", out2, duration=4.0)
    saa = json.loads(out2.read_text(encoding="utf-8"))
    assert saa["segments"][0]["speaker"] == "SPEAKER_00"
    assert saa["segments"][1]["speaker"] == "SPEAKER_01"


@pytest.mark.unit
def test_jsonl_and_explicit_times(tmp_path: Path) -> None:
    src = tmp_path / "in.jsonl"
    src.write_text(
        '{"start": 1.0, "end": 2.5, "text": "timed", "speaker_id": 2}\n',
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    convert_file(src, out, time_offset=10.0)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["segments"][0]["start"] == pytest.approx(11.0)
    assert data["segments"][0]["end"] == pytest.approx(12.5)
    assert data["segments"][0]["speaker"] == "SPEAKER_01"
