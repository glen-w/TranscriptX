"""Tests for Nemotron dump → WhisperX converter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from transcriptx.services.transcription.nemotron_json_to_whisperx import (
    convert_file,
    load_segments_from_path,
    main as converter_main,
    segments_from_payload,
    speaker_label,
)

_FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "transcripts"


@pytest.mark.unit
def test_speaker_label_zero_based() -> None:
    assert speaker_label(0) == "SPEAKER_00"
    assert speaker_label("<spk:1>") == "SPEAKER_01"
    assert speaker_label("SPEAKER_02") == "SPEAKER_02"


@pytest.mark.unit
def test_convert_ctc_words_golden(tmp_path: Path) -> None:
    fixture = _FIXTURES / "nemotron" / "ctc_words.json"
    expected = _FIXTURES / "whisperx" / "from_nemotron_ctc.json"
    out = tmp_path / "out.json"
    convert_file(fixture, out)
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(
        expected.read_text(encoding="utf-8")
    )


@pytest.mark.unit
def test_convert_spk_tags_golden(tmp_path: Path) -> None:
    fixture = _FIXTURES / "nemotron" / "spk_tags.json"
    expected = _FIXTURES / "whisperx" / "from_nemotron_spk_tags.json"
    out = tmp_path / "out.json"
    convert_file(fixture, out)
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(
        expected.read_text(encoding="utf-8")
    )


@pytest.mark.unit
def test_convert_undiarized_golden(tmp_path: Path) -> None:
    fixture = _FIXTURES / "nemotron" / "undiarized.json"
    expected = _FIXTURES / "whisperx" / "from_nemotron_undiarized.json"
    out = tmp_path / "out.json"
    convert_file(fixture, out)
    assert json.loads(out.read_text(encoding="utf-8")) == json.loads(
        expected.read_text(encoding="utf-8")
    )
    segments = load_segments_from_path(fixture)
    assert len(segments) == 1
    assert "speaker" not in segments[0]


@pytest.mark.unit
def test_ctc_error_falls_back_to_tags() -> None:
    payload = {
        "text": "<spk:0> Hello",
        "ctc_timestamps": {"error": "alignment failed", "words": []},
    }
    segments = segments_from_payload(payload)
    assert segments[0]["speaker"] == "SPEAKER_00"
    assert segments[0]["text"] == "Hello"


@pytest.mark.unit
def test_extract_speaker_dict_turns() -> None:
    payload = {
        "turns": [
            {"speaker": 0, "text": "Hello", "start": 0.0, "end": 0.5},
            {"speaker": 1, "text": "Hi", "start": 0.5, "end": 0.9},
        ]
    }
    segments = segments_from_payload(payload)
    assert [s["speaker"] for s in segments] == ["SPEAKER_00", "SPEAKER_01"]


@pytest.mark.unit
def test_convert_jsonl_and_cli(tmp_path: Path) -> None:
    inp = tmp_path / "raw.jsonl"
    inp.write_text(
        '{"text": "<spk:0> Hello"}\n{"text": "<spk:1> Hi"}\n',
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    assert converter_main(["--input", str(inp), "--output", str(out)]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [s["speaker"] for s in data["segments"]] == ["SPEAKER_00", "SPEAKER_01"]
