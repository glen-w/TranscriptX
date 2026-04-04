"""Tests for highlights and summary Markdown renderers."""

from __future__ import annotations

from transcriptx.core.analysis.highlights import render_highlights_markdown
from transcriptx.core.analysis.summary import render_summary_markdown


def test_highlights_markdown_includes_anchors() -> None:
    results = {
        "inputs": {"used_sentiment": True, "used_emotion": False},
        "sections": {
            "cold_open": {
                "items": [
                    {
                        "speaker": "Emma",
                        "quote": "Let us begin.",
                        "start": 10.0,
                        "end": 15.0,
                        "segment_refs": {"segment_indexes": [3]},
                        "score": {"total": 0.7},
                    }
                ]
            },
            "conflict_points": {"events": []},
            "emblematic_phrases": {"phrases": []},
        },
    }
    md = render_highlights_markdown(results)
    assert "[0:10-0:15 | Emma | seg#3]" in md
    assert "Provenance" in md


def test_highlights_markdown_no_signal() -> None:
    results = {
        "inputs": {"used_sentiment": False, "used_emotion": False},
        "sections": {
            "cold_open": {"items": []},
            "conflict_points": {"events": []},
            "emblematic_phrases": {"phrases": []},
        },
    }
    md = render_highlights_markdown(results)
    assert "No strong signal detected" in md
    assert "Provenance" in md


def test_summary_markdown_anchor_quote() -> None:
    summary_payload = {
        "inputs": {
            "used_sentiment": True,
            "used_emotion": True,
            "used_highlights": True,
            "highlights_source": "context",
        },
        "overview": {"paragraph": "Short overview."},
        "key_themes": {"bullets": [{"text": "Theme 1"}]},
        "tension_points": {
            "bullets": [
                {
                    "text": "Tension spike involving two speakers.",
                    "anchor_quote": {
                        "speaker": "Noah",
                        "quote": "We disagree.",
                        "start": 30.0,
                        "end": 33.0,
                        "segment_refs": {"segment_indexes": [8]},
                    },
                }
            ]
        },
        "commitments": {"items": []},
    }
    md = render_summary_markdown(summary_payload)
    assert "[0:30-0:33 | Noah | seg#8]" in md
    assert "Provenance" in md


def test_summary_markdown_no_signal() -> None:
    summary_payload = {
        "inputs": {
            "used_sentiment": False,
            "used_emotion": False,
            "used_highlights": False,
            "highlights_source": "missing",
        },
        "overview": {"paragraph": ""},
        "key_themes": {"bullets": []},
        "tension_points": {"bullets": []},
        "commitments": {"items": []},
    }
    md = render_summary_markdown(summary_payload)
    assert "No strong signal detected" in md
    assert "Provenance" in md
