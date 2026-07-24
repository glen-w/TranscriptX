"""Intake and dedupe tests for semantic_similarity."""

from __future__ import annotations

from transcriptx.core.analysis.semantic_similarity.intake import (
    dedupe_text_index,
    segment_rows_from_dicts,
)


def test_segment_rows_filters_short_and_filler() -> None:
    rows, meta = segment_rows_from_dicts(
        [
            {"text": "hi", "start": 0, "end": 1, "speaker": "A", "speaker_db_id": 1},
            {"text": "um", "start": 1, "end": 2, "speaker": "A", "speaker_db_id": 1},
            {
                "text": "one two three four",
                "start": 2,
                "end": 3,
                "speaker": "A",
                "speaker_db_id": 1,
            },
        ],
        min_words=3,
    )
    assert len(rows) == 1
    assert meta["skipped_reasons"]["too_short"] == 1


def test_dedupe_text_index() -> None:
    rows, _ = segment_rows_from_dicts(
        [
            {
                "text": "same phrase",
                "start": 0,
                "end": 1,
                "speaker": "A",
                "speaker_db_id": 1,
            },
            {
                "text": "SAME PHRASE",
                "start": 1,
                "end": 2,
                "speaker": "B",
                "speaker_db_id": 2,
            },
        ],
        min_words=2,
    )
    d = dedupe_text_index(rows)
    assert len(d) == 1
