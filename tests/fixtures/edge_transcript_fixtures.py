"""
Fixtures for edge-case transcripts.
"""

import json
from pathlib import Path
from typing import Any, Dict

import pytest

_SOURCE = {
    "type": "manual",
    "original_path": "edge.json",
    "imported_at": "2026-01-01T00:00:00Z",
}


def _v1_doc(segments: list) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "source": dict(_SOURCE),
        "segments": segments,
    }


@pytest.fixture
def edge_transcript_empty() -> Dict[str, Any]:
    return _v1_doc([])


@pytest.fixture
def edge_transcript_ultrashort() -> Dict[str, Any]:
    return _v1_doc([{"speaker": "SPEAKER_00", "text": "Hi", "start": 0.0, "end": 0.2}])


@pytest.fixture
def edge_transcript_overlapping() -> Dict[str, Any]:
    return _v1_doc(
        [
            {"speaker": "SPEAKER_00", "text": "First", "start": 0.0, "end": 2.0},
            {"speaker": "SPEAKER_01", "text": "Overlap", "start": 1.5, "end": 3.0},
        ]
    )


@pytest.fixture
def edge_transcript_weird_timestamps() -> Dict[str, Any]:
    return _v1_doc(
        [
            {"speaker": "SPEAKER_00", "text": "Zero", "start": 0.0, "end": 0.0},
            {"speaker": "SPEAKER_00", "text": "Out of order", "start": 5.0, "end": 4.9},
        ]
    )


@pytest.fixture
def edge_transcript_unknown_speaker() -> Dict[str, Any]:
    # Canonical v1.0 requires non-empty structural speaker label
    return _v1_doc(
        [
            {
                "speaker": "SPEAKER_XX",
                "text": "Unknown speaker",
                "start": 0.0,
                "end": 1.0,
            }
        ]
    )


@pytest.fixture
def edge_transcript_weird_punctuation() -> Dict[str, Any]:
    return _v1_doc(
        [
            {
                "speaker": "SPEAKER_00",
                "text": "Wait... what?! ##!!",
                "start": 0.0,
                "end": 1.0,
            }
        ]
    )


@pytest.fixture
def edge_transcript_large() -> Dict[str, Any]:
    segments = [
        {
            "speaker": f"SPEAKER_{i % 3:02d}",
            "text": f"Segment {i}",
            "start": float(i),
            "end": float(i + 0.5),
        }
        for i in range(200)
    ]
    return _v1_doc(segments)


@pytest.fixture
def edge_transcript_file_factory(tmp_path):
    def _write(data: Dict[str, Any], name: str = "edge_transcript.json") -> Path:
        file_path = tmp_path / name
        file_path.write_text(json.dumps(data, indent=2))
        return file_path

    return _write
