from transcriptx.core.analysis.highlights.core import (  # type: ignore[import-untyped]
    SegmentLite,
    compute_highlights,
)
from transcriptx.core.utils.config.analysis import (  # type: ignore[import-untyped]
    HighlightsConfig,
)


def _segment(
    idx: int,
    speaker: str,
    text: str,
    start: float,
    end: float,
    sentiment: float | None = None,
) -> SegmentLite:
    return SegmentLite(
        segment_key=f"idx:test:{idx}",
        segment_db_id=None,
        segment_uuid=None,
        segment_index=idx,
        speaker_display=speaker,
        speaker_id=None,
        start=start,
        end=end,
        text=text,
        sentiment_compound=sentiment,
    )


def test_unnamed_speakers_excluded() -> None:
    cfg = HighlightsConfig()
    segments = [
        _segment(0, "SPEAKER_01", "hello world", 0.0, 1.0),
        _segment(1, "Alice", "We should do this now.", 1.5, 2.5, sentiment=0.4),
    ]
    result = compute_highlights(segments, cfg)
    cold_open = result["sections"]["cold_open"]["items"]
    assert all(item["speaker"] != "SPEAKER_01" for item in cold_open)


def test_deterministic_ids() -> None:
    cfg = HighlightsConfig()
    segments = [
        _segment(0, "Alice", "We should do this now.", 0.0, 1.0, sentiment=0.4),
        _segment(1, "Bob", "I disagree with that.", 1.2, 2.0, sentiment=-0.6),
    ]
    first = compute_highlights(segments, cfg)
    second = compute_highlights(segments, cfg)
    first_ids = [item["id"] for item in first["sections"]["cold_open"]["items"]]
    second_ids = [item["id"] for item in second["sections"]["cold_open"]["items"]]
    assert first_ids == second_ids


def test_max_consecutive_speaker() -> None:
    cfg = HighlightsConfig()
    cfg.thresholds.max_consecutive_per_speaker = 1
    segments = [
        _segment(0, "Alice", "Point one.", 0.0, 1.0, sentiment=0.1),
        _segment(1, "Alice", "Point two.", 1.1, 2.0, sentiment=0.2),
        _segment(2, "Bob", "Counterpoint.", 2.1, 3.0, sentiment=-0.4),
    ]
    result = compute_highlights(segments, cfg)
    speakers = [item["speaker"] for item in result["sections"]["cold_open"]["items"]]
    for idx in range(1, len(speakers)):
        assert speakers[idx] != speakers[idx - 1]
