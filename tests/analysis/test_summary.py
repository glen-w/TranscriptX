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


def test_overview_mentions_themes_and_speakers() -> None:
    highlights = {
        "transcript_key": "unknown",
        "sections": {
            "emblematic_phrases": {
                "phrases": [{"phrase": "roadmap", "score": {"total": 0.5}}]
            },
            "conflict_points": {"events": []},
            "cold_open": {
                "items": [
                    {
                        "speaker": "Alice",
                        "quote": "roadmap discussion",
                        "start": 0.0,
                        "end": 1.0,
                        "segment_refs": {"segment_indexes": [0]},
                        "score": {"total": 0.6},
                    }
                ]
            },
        },
    }
    segments = [
        _segment(0, "Alice", "roadmap discussion", 0.0, 1.0),
    ]
    cfg = SummaryConfig()
    result = compute_summary(highlights, segments, cfg)
    para = result["overview"]["paragraph"]
    assert "roadmap" in para.lower()
    assert "named speakers" in para.lower()
    assert "opening moments focused on roadmap" in para.lower()


def test_overview_mentions_conflict_participants() -> None:
    highlights = {
        "transcript_key": "unknown",
        "sections": {
            "emblematic_phrases": {"phrases": []},
            "conflict_points": {
                "events": [
                    {
                        "event_id": "conflict-1",
                        "participants": [
                            {"speaker_display": "Eve", "speaker_id": 1},
                            {"speaker_display": "Sam", "speaker_id": 2},
                        ],
                    }
                ]
            },
            "cold_open": {"items": []},
        },
    }
    segments = [
        _segment(0, "Eve", "x", 0.0, 1.0),
        _segment(1, "Sam", "y", 1.0, 2.0),
    ]
    cfg = SummaryConfig()
    result = compute_summary(highlights, segments, cfg)
    para = result["overview"]["paragraph"]
    assert "Eve" in para
    assert "Sam" in para
    assert "tension" in para.lower()


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


def test_summary_filters_filler_themes_in_overview_and_key_themes() -> None:
    highlights = {
        "transcript_key": "unknown",
        "sections": {
            "emblematic_phrases": {
                "phrases": [
                    {"phrase": "kind of", "score": {"total": 0.9}},
                    {"phrase": "i think", "score": {"total": 0.8}},
                    {"phrase": "budget risk", "score": {"total": 0.7}},
                ]
            },
            "conflict_points": {"events": []},
            "cold_open": {"items": []},
        },
    }
    segments = [_segment(0, "Alice", "We should mitigate budget risk.", 0.0, 60.0)]
    cfg = SummaryConfig()

    result = compute_summary(highlights, segments, cfg)
    overview = result["overview"]["paragraph"].lower()
    key_themes = [row["text"].lower() for row in result["key_themes"]["bullets"]]

    assert "kind of" not in overview
    assert "i think" not in overview
    assert "budget risk" in overview
    assert "kind of" not in key_themes
    assert "i think" not in key_themes
    assert "budget risk" in key_themes
