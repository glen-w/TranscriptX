from transcriptx.core.analysis.highlights.core import (  # type: ignore[import-untyped]
    SegmentLite,
)
from transcriptx.core.analysis.summary.core import (  # type: ignore[import-untyped]
    compute_summary,
)
from transcriptx.core.utils.config.analysis import (  # type: ignore[import-untyped]
    SummaryConfig,
)


def _segment(
    idx: int, speaker: str, text: str, start: float, end: float
) -> SegmentLite:
    return SegmentLite(
        segment_key=f"idx:test:{idx}",
        segment_db_id=None,
        segment_uuid=None,
        segment_index=idx,
        speaker_display=speaker,
        speaker_id=idx,
        start=start,
        end=end,
        text=text,
    )


def test_commitment_extraction_contains_span() -> None:
    cfg = SummaryConfig()
    segments = [
        _segment(0, "Alice", "We will deliver the report tomorrow.", 0.0, 1.0),
    ]
    highlights = {
        "sections": {
            "emblematic_phrases": {"phrases": []},
            "conflict_points": {"events": []},
            "cold_open": {"items": []},
        }
    }
    result = compute_summary(highlights, segments, cfg)
    commitments = result["commitments"]["items"]
    assert commitments, "Expected at least one commitment"
    assert commitments[0]["extraction"]["span_text"]
    assert commitments[0]["extraction"]["span_start_char"] is not None
