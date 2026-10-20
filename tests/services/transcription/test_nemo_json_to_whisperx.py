"""Tests for NeMo JSONL → WhisperX converter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.services.transcription.nemo_json_to_whisperx import (
    convert_file,
    load_segments_from_path,
)


@pytest.mark.unit
def test_convert_jsonl_to_whisperx_shape(tmp_path: Path) -> None:
    inp = tmp_path / "hyp.jsonl"
    inp.write_text(
        '{"start": 0.0, "end": 1.5, "text": "hello"}\n'
        '{"start": 1.5, "end": 3.0, "text": "world", "speaker": "SPEAKER_00"}\n',
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    convert_file(inp, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "segments" in data
    assert len(data["segments"]) == 2
    assert data["segments"][0]["text"] == "hello"


@pytest.mark.unit
def test_load_fixture_whisperx_from_nemo(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2] / "fixtures" / "transcripts"
    fixture = root / "nemo" / "sample.jsonl"
    expected = root / "whisperx" / "from_nemo.json"
    assert fixture.is_file()
    out = tmp_path / "out.json"
    convert_file(fixture, out)
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(
        expected.read_text(encoding="utf-8")
    )
    segments = load_segments_from_path(fixture)
    assert len(segments) >= 1
