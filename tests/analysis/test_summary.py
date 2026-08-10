"""Tests for summary."""

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
                    {
                        "phrase": "kind of",
                        "score": {"total": 0.9},
                        "tokens": ["kind", "of"],
                    },
                    {
                        "phrase": "i think",
                        "score": {"total": 0.8},
                        "tokens": ["i", "think"],
                    },
                    {
                        "phrase": "of course",
                        "score": {"total": 0.85},
                        "tokens": ["of", "course"],
                    },
                    {
                        "phrase": "need to",
                        "score": {"total": 0.84},
                        "tokens": ["need", "to"],
                    },
                    {
                        "phrase": "going to",
                        "score": {"total": 0.83},
                        "tokens": ["going", "to"],
                    },
                    {
                        "phrase": "for example",
                        "score": {"total": 0.82},
                        "tokens": ["for", "example"],
                    },
                    {
                        "phrase": "budget risk",
                        "score": {"total": 0.7},
                        "tokens": ["budget", "risk"],
                        "canonical_key": "budget risk",
                    },
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
    # Overview focus requires high-tier theme labels; emblematic-only phrases
    # must not invent a focus clause (Theme A honesty).
    assert "kind of" not in overview
    assert "centered on kind of" not in overview
    assert "kind of" not in key_themes
    assert "i think" not in key_themes
    assert "of course" not in key_themes
    assert "need to" not in key_themes
    assert "going to" not in key_themes
    assert "for example" not in key_themes
    assert "budget risk" in key_themes
    assert result["phrase_quality_version"] >= 2
    assert result["key_themes"]["bullets"], "expected useful themes without LLM"


def test_overview_uses_theme_labels_and_minutes() -> None:
    highlights = {
        "transcript_key": "sess",
        "themes": [
            {
                "label": "Budget risk",
                "quote_ids": ["q1"],
                "is_unthemed": False,
            },
            {
                "label": "Launch planning",
                "quote_ids": ["q2"],
                "is_unthemed": False,
            },
        ],
        "sections": {
            "emblematic_phrases": {"phrases": []},
            "conflict_points": {"events": []},
            "cold_open": {"items": []},
        },
    }
    segments = [
        _segment(0, "Alice", "budget talk", 0.0, 125.0),
        _segment(1, "Bob", "launch talk", 125.0, 130.0),
    ]
    result = compute_summary(highlights, segments, SummaryConfig())
    para = result["overview"]["paragraph"]
    assert "Budget risk" in para
    assert "Launch planning" in para
    assert "minutes" in para.lower()


def test_overview_conflict_and_others_truncation() -> None:
    participants = [
        {"speaker_display": name, "speaker_id": i}
        for i, name in enumerate(["A", "B", "C", "D", "E"], start=1)
    ]
    highlights = {
        "sections": {
            "emblematic_phrases": {"phrases": []},
            "conflict_points": {
                "events": [
                    {"event_id": "c1", "participants": participants},
                ]
            },
            "cold_open": {"items": []},
        }
    }
    segments = [_segment(0, "A", "x", 0.0, 1.0)]
    para = compute_summary(highlights, segments, SummaryConfig())["overview"][
        "paragraph"
    ]
    assert "and others" in para


def test_key_themes_prefers_noun_tiers_then_diversifies() -> None:
    highlights = {
        "sections": {
            "emblematic_phrases": {
                "phrases": [
                    {
                        "phrase": "budget risk",
                        "tokens": ["budget", "risk"],
                        "canonical_key": "budget risk",
                        "score": {"total": 0.5},
                        "examples": [],
                    },
                    {
                        "phrase": "timeline risk",
                        "tokens": ["timeline", "risk"],
                        "canonical_key": "timeline risk",
                        "score": {"total": 0.49},
                        "examples": [],
                    },
                    {
                        "phrase": "launch planning",
                        "tokens": ["launch", "planning"],
                        "canonical_key": "launch planning",
                        "score": {"total": 0.48},
                        "examples": [],
                    },
                    {
                        "phrase": "",
                        "tokens": [],
                        "score": {"total": 0.99},
                    },
                ]
            },
            "conflict_points": {"events": []},
            "cold_open": {"items": []},
        }
    }
    bullets = compute_summary(
        highlights, [_segment(0, "Alice", "x", 0.0, 1.0)], SummaryConfig()
    )["key_themes"]["bullets"]
    texts = [b["text"] for b in bullets]
    assert "budget risk" in texts
    assert "" not in texts


def test_commitments_respect_max_per_owner() -> None:
    cfg = SummaryConfig()
    cfg.commitments.max_per_owner = 1
    segments = [
        _segment(0, "Alice", "We will deliver the report tomorrow.", 0.0, 1.0),
        _segment(1, "Alice", "I will follow up with the client.", 1.0, 2.0),
        _segment(2, "Bob", "We will ship the release Friday.", 2.0, 3.0),
    ]
    highlights = {
        "sections": {
            "emblematic_phrases": {"phrases": []},
            "conflict_points": {"events": []},
            "cold_open": {"items": []},
        }
    }
    items = compute_summary(highlights, segments, cfg)["commitments"]["items"]
    alice = [i for i in items if i["owner_display"] == "Alice"]
    assert len(alice) <= 1
    assert any(i["owner_display"] == "Bob" for i in items)


def test_overview_omits_focus_when_only_filler_phrases() -> None:
    highlights = {
        "transcript_key": "unknown",
        "sections": {
            "emblematic_phrases": {
                "phrases": [
                    {
                        "phrase": "kind of",
                        "score": {"total": 0.9},
                        "tokens": ["kind", "of"],
                    },
                    {
                        "phrase": "of course",
                        "score": {"total": 0.8},
                        "tokens": ["of", "course"],
                    },
                ]
            },
            "conflict_points": {"events": []},
            "cold_open": {"items": []},
        },
    }
    segments = [_segment(0, "Alice", "kind of of course", 0.0, 30.0)]
    result = compute_summary(highlights, segments, SummaryConfig())
    para = result["overview"]["paragraph"].lower()
    assert "centered on" not in para
    assert "kind of" not in para
    assert "of course" not in para
    assert "named speakers" in para


def test_commitment_rejects_light_verb_only_stems() -> None:
    cfg = SummaryConfig()
    segments = [
        _segment(0, "Alice", "We need to.", 0.0, 1.0),
        _segment(1, "Bob", "We will deliver the migration plan.", 1.0, 2.0),
    ]
    highlights = {
        "sections": {
            "emblematic_phrases": {"phrases": []},
            "conflict_points": {"events": []},
            "cold_open": {"items": []},
        }
    }
    items = compute_summary(highlights, segments, cfg)["commitments"]["items"]
    actions = [i["action"].lower() for i in items]
    assert not any(a.strip() in {"we need to", "we need to."} for a in actions)
    assert any("deliver" in a for a in actions)
