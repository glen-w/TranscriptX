"""Blessed get_segments entry point."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.segments import get_segments


@pytest.mark.unit
def test_get_segments_empty_target_returns_empty() -> None:
    assert get_segments("", cache=False) == []


@pytest.mark.unit
def test_get_segments_cache_false_loads_via_io(tmp_path: Path) -> None:
    p = tmp_path / "t.json"
    payload = {
        "schema_version": 1,
        "source": {
            "type": "manual",
            "original_path": "test.json",
            "imported_at": "2026-01-01T00:00:00Z",
        },
        "segments": [{"text": "hi", "speaker": "A", "start": 0.0, "end": 1.0}],
    }
    p.write_text(json.dumps(payload), encoding="utf-8")
    out = get_segments(p, cache=False)
    assert len(out) == 1
    assert out[0]["text"] == "hi"


@pytest.mark.unit
def test_get_segments_cache_true_uses_transcript_service(tmp_path: Path) -> None:
    p = tmp_path / "t.json"
    p.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": {
                    "type": "manual",
                    "original_path": "test.json",
                    "imported_at": "2026-01-01T00:00:00Z",
                },
                "segments": [],
            }
        ),
        encoding="utf-8",
    )
    svc = MagicMock()
    svc.load_segments.return_value = [{"text": "cached"}]
    with patch("transcriptx.io.get_transcript_service", return_value=svc):
        out = get_segments(p, cache=True)
    assert out == [{"text": "cached"}]
    svc.load_segments.assert_called_once()
