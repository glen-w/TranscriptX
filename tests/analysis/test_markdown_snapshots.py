from pathlib import Path

from transcriptx.core.analysis.highlights import (  # type: ignore[import-untyped]
    render_highlights_markdown,
)
from transcriptx.core.analysis.summary import (  # type: ignore[import-untyped]
    render_summary_markdown,
)

from tests.analysis.markdown_utils import normalize_markdown


FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "expected_outputs"


def test_highlights_markdown_snapshot() -> None:
    highlights = {
        "sections": {
            "cold_open": {
                "items": [
                    {"speaker": "Alice", "quote": "Opening remark."},
                ]
            },
            "conflict_points": {
                "events": [{"anchor_quote": {"speaker": "Bob", "quote": "I disagree."}}]
            },
            "emblematic_phrases": {"phrases": [{"phrase": "key phrase"}]},
        }
    }
    expected = (FIXTURES_DIR / "highlights" / "highlights.md").read_text()
    actual = render_highlights_markdown(highlights)
    assert normalize_markdown(actual) == normalize_markdown(expected)


def test_summary_markdown_snapshot() -> None:
    summary = {
        "inputs": {
            "used_highlights": True,
            "highlights_source": "context",
            "used_sentiment": False,
            "used_emotion": True,
        },
        "overview": {"paragraph": "Overview paragraph."},
        "key_themes": {"bullets": [{"text": "Theme A"}]},
        "tension_points": {
            "bullets": [
                {
                    "text": "Tension here.",
                    "anchor_quote": {"speaker": "Alice", "quote": "Anchor quote."},
                }
            ]
        },
        "commitments": {"items": [{"owner_display": "Alice", "action": "Do X"}]},
    }
    expected = (FIXTURES_DIR / "summary" / "summary.md").read_text()
    actual = render_summary_markdown(summary)
    assert normalize_markdown(actual) == normalize_markdown(expected)
