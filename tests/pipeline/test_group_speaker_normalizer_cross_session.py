"""Cross-session speaker normalization for group analysis."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import (
    normalize_speakers_across_transcripts,
)


def _result(path: str, order: int = 0) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=path,
        transcript_key=path,
        run_id=f"r{order}",
        order_index=order,
        output_dir=f"/out/{order}",
        module_results={},
    )


@pytest.mark.unit
def test_same_display_name_across_sessions_shares_canonical_id() -> None:
    segments_by_path = {
        "/a.json": [{"speaker": "Alice", "text": "Hi", "start": 0.0, "end": 1.0}],
        "/b.json": [{"speaker": "Alice", "text": "Again", "start": 0.0, "end": 1.0}],
    }

    def load_segments(path, use_cache=True):
        return segments_by_path[path]

    with patch(
        "transcriptx.core.pipeline.speaker_normalizer.TranscriptService"
    ) as mock_ts:
        mock_ts.return_value.load_segments.side_effect = load_segments
        out = normalize_speakers_across_transcripts(
            [_result("/a.json", 0), _result("/b.json", 1)]
        )

    id_a = out.transcript_to_speakers["/a.json"]["Alice"]
    id_b = out.transcript_to_speakers["/b.json"]["Alice"]
    assert id_a == id_b
    assert out.canonical_to_display[id_a] == "Alice"


@pytest.mark.unit
def test_different_display_names_get_distinct_canonical_ids() -> None:
    with patch(
        "transcriptx.core.pipeline.speaker_normalizer.TranscriptService"
    ) as mock_ts:
        mock_ts.return_value.load_segments.side_effect = [
            [{"speaker": "Alice", "text": "Hi", "start": 0.0, "end": 1.0}],
            [{"speaker": "Bob", "text": "Yo", "start": 0.0, "end": 1.0}],
        ]
        out = normalize_speakers_across_transcripts(
            [_result("/a.json", 0), _result("/b.json", 1)]
        )

    assert (
        out.transcript_to_speakers["/a.json"]["Alice"]
        != out.transcript_to_speakers["/b.json"]["Bob"]
    )


@pytest.mark.unit
def test_empty_display_name_falls_back_to_local_id() -> None:
    with (
        patch(
            "transcriptx.core.pipeline.speaker_normalizer.TranscriptService"
        ) as mock_ts,
        patch(
            "transcriptx.core.pipeline.speaker_normalizer.get_unique_speakers",
            return_value={"local-1": ""},
        ),
    ):
        mock_ts.return_value.load_segments.return_value = [
            {"speaker": "local-1", "text": "anon", "start": 0.0, "end": 1.0},
        ]
        out = normalize_speakers_across_transcripts([_result("/a.json")])

    assert out.transcript_to_speakers["/a.json"]["local-1"]
    assert out.transcript_to_display["/a.json"]["local-1"] == "local-1"
    assert (
        out.canonical_to_display[out.transcript_to_speakers["/a.json"]["local-1"]]
        == "local-1"
    )
