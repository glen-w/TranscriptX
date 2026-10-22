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


_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "transcripts"


def _assert_converts_to_golden(tmp_path: Path, source: Path, expected: Path) -> None:
    out = tmp_path / "out.json"
    convert_file(source, out)
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(
        expected.read_text(encoding="utf-8")
    )


@pytest.mark.unit
def test_load_fixture_whisperx_from_nemo(tmp_path: Path) -> None:
    fixture = _FIXTURE_ROOT / "nemo" / "sample.jsonl"
    expected = _FIXTURE_ROOT / "whisperx" / "from_nemo.json"
    assert fixture.is_file()
    _assert_converts_to_golden(tmp_path, fixture, expected)
    segments = load_segments_from_path(fixture)
    assert len(segments) >= 1


@pytest.mark.unit
def test_pred_text_and_blank_lines_golden(tmp_path: Path) -> None:
    _assert_converts_to_golden(
        tmp_path,
        _FIXTURE_ROOT / "nemo" / "pred_text.jsonl",
        _FIXTURE_ROOT / "whisperx" / "from_nemo_pred_text.json",
    )


@pytest.mark.unit
def test_list_json_optional_speaker_golden(tmp_path: Path) -> None:
    _assert_converts_to_golden(
        tmp_path,
        _FIXTURE_ROOT / "nemo" / "list.json",
        _FIXTURE_ROOT / "whisperx" / "from_nemo_list.json",
    )
    segments = load_segments_from_path(_FIXTURE_ROOT / "nemo" / "list.json")
    assert segments[0]["speaker"] == "SPEAKER_00"
    assert "speaker" not in segments[1]


@pytest.mark.unit
def test_wrapped_segments_json(tmp_path: Path) -> None:
    inp = tmp_path / "wrapped.json"
    inp.write_text(
        json.dumps(
            {
                "segments": [
                    {"start": 0, "end": 1, "text": "wrap"},
                    {"start": 1, "end": 2, "pred_text": ""},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    convert_file(inp, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["segments"] == [{"start": 0.0, "end": 1.0, "text": "wrap"}]
