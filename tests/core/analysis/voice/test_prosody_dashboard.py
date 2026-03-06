from __future__ import annotations

from typing import Any

import pytest

from transcriptx.core.analysis.voice.dashboard import resolve_segment_metadata


class _DummyContext:
    def __init__(self, segments: list[dict[str, Any]], transcript_key: str) -> None:
        self._segments = segments
        self._transcript_key = transcript_key

    def get_segments(self) -> list[dict[str, Any]]:
        return self._segments

    def get_transcript_key(self) -> str:
        return self._transcript_key


def test_resolve_segment_metadata_includes_duration_and_id() -> None:
    ctx = _DummyContext(
        segments=[
            {"start": 0.0, "end": 1.5, "speaker": "Alice", "text": "Hello there."},
            {"start": 2.0, "end": 3.2, "speaker": "Bob", "text": "Reply."},
        ],
        transcript_key="dummy_key",
    )
    df = resolve_segment_metadata(ctx)
    assert "segment_id" in df.columns
    assert "duration_s" in df.columns
    assert df["duration_s"].iloc[0] == pytest.approx(1.5)
    assert df["duration_s"].iloc[1] == pytest.approx(1.2)
