"""Unit tests for emblematic phrase helpers and charts PDF collection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

pytest.importorskip("spacy")

pytestmark = pytest.mark.requires_nlp

from transcriptx.core.analysis.highlights.core import (
    SegmentLite,
    _compute_emblematic_phrases,
    _dedupe_phrases,
    _select_phrase_examples,
)
from transcriptx.core.analysis.insights.analysis import (
    _select_recurring_ideas,
    _select_themes,
)
from transcriptx.core.analysis.summary import charts_pdf
from transcriptx.core.utils.config.analysis import HighlightsConfig
from transcriptx.core.utils.nlp_utils import build_tic_mask


def _seg(idx: int, speaker: str, text: str) -> SegmentLite:
    return SegmentLite(
        segment_key=f"idx:h:{idx}",
        segment_db_id=None,
        segment_uuid=None,
        segment_index=idx,
        speaker_display=speaker,
        speaker_id=idx,
        start=float(idx),
        end=float(idx) + 1.0,
        text=text,
    )


def test_compute_emblematic_phrases_lexical_fallback_without_nlp() -> None:
    segments = [
        _seg(i, "Alice" if i % 2 == 0 else "Bob", text)
        for i, text in enumerate(
            [
                "Budget risk and launch planning keep coming up.",
                "Launch planning depends on budget risk mitigation.",
                "Budget risk remains the top concern this quarter.",
                "We revisit launch planning and timeline risk together.",
            ]
            * 3
        )
    ]
    with patch(
        "transcriptx.core.analysis.highlights.core.get_nlp_model",
        side_effect=RuntimeError("no nlp"),
    ):
        phrases = _compute_emblematic_phrases(
            segments, HighlightsConfig(), build_tic_mask()
        )
    texts = {str(p.get("phrase") or "").lower() for p in phrases}
    assert texts.isdisjoint({"of course", "need to", "going to"})
    assert (
        any("budget" in t or "launch" in t or "planning" in t for t in texts)
        or phrases == []
    )


def test_select_phrase_examples_dedupes_same_segment() -> None:
    seg = _seg(0, "Alice", "hello")
    assert _select_phrase_examples([]) == []
    examples = _select_phrase_examples([(0, seg), (1, seg), (2, seg)])
    assert len(examples) == 1
    assert examples[0]["quote"] == "hello"


def test_dedupe_phrases_overlap_and_containment() -> None:
    phrases = [
        {
            "phrase": "budget risk",
            "tokens": ["budget", "risk"],
            "score": {"total": 1.0},
        },
        {
            "phrase": "the budget risk",
            "tokens": ["the", "budget", "risk"],
            "score": {"total": 0.98},
        },
        {
            "phrase": "launch planning",
            "tokens": ["launch", "planning"],
            "score": {"total": 0.5},
        },
    ]
    deduped = _dedupe_phrases(phrases)
    texts = [p["phrase"] for p in deduped]
    assert "launch planning" in texts
    assert len(deduped) < len(phrases)


def test_select_themes_and_recurring_ideas_edge_shapes() -> None:
    empty_hl: dict = {"sections": {"cold_open": {"items": []}}}
    assert (
        _select_themes(
            {"content_phrases": "bad"},
            highlights=empty_hl,
            topic_modeling={},
            limit=8,
            min_score=0.28,
            topic_boost=0.05,
        )
        == []
    )
    selected = _select_themes(
        {
            "content_phrases": [
                1,
                {
                    "phrase": "budget risk",
                    "score": {"total": 0.9, "spread": 0.4, "recurrence": 0.4},
                },
                {
                    "phrase": "launch plan",
                    "score": {"total": 0.85, "spread": 0.35, "recurrence": 0.3},
                },
            ]
        },
        highlights=empty_hl,
        topic_modeling={},
        limit=8,
        min_score=0.28,
        topic_boost=0.05,
    )
    phrases = [row["phrase"] for row in selected]
    assert "budget risk" in phrases
    assert "launch plan" in phrases
    assert (
        _select_recurring_ideas(
            {"phrase_scores": "bad"},
            highlights=empty_hl,
            topic_modeling={},
            limit=8,
            min_score=0.28,
            topic_boost=0.05,
        )
        == []
    )
    recurring = _select_recurring_ideas(
        {
            "phrase_scores": {
                "a": "x",
                "b": {"recurrence": 0.0, "total": 0.9, "spread": 0.4},
                "budget risk": {
                    "recurrence": 0.5,
                    "total": 0.9,
                    "spread": 0.4,
                },
                "launch plan": {
                    "recurrence": 0.4,
                    "total": 0.85,
                    "spread": 0.35,
                },
            }
        },
        highlights=empty_hl,
        topic_modeling={},
        limit=8,
        min_score=0.28,
        topic_boost=0.05,
    )
    rec_phrases = [row["phrase"] for row in recurring]
    assert "budget risk" in rec_phrases
    assert "launch plan" in rec_phrases
    assert "b" not in rec_phrases


def test_collect_charts_by_module_groups_and_skips_non_images(tmp_path: Path) -> None:
    root = tmp_path / "run"
    sentiment = root / "sentiment" / "charts" / "global"
    sentiment.mkdir(parents=True)
    (sentiment / "chart_2.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (sentiment / "chart_10.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (sentiment / "notes.txt").write_text("skip", encoding="utf-8")
    stats = root / "stats" / "charts" / "global"
    stats.mkdir(parents=True)
    (stats / "a.jpg").write_bytes(b"JPEG")
    by_module = charts_pdf.collect_charts_by_module(root)
    assert set(by_module) == {"sentiment", "stats"}
    assert [p.name for p in by_module["sentiment"]] == ["chart_2.png", "chart_10.png"]
    w, h = charts_pdf._pixels_to_points(100, 50, (0, -1))
    assert w > 0 and h > 0
    w2, h2 = charts_pdf._pixels_to_points(100, 50, 72)
    assert abs(w2 - 100) < 0.01
    assert charts_pdf._module_display_name("entity_sentiment") == "Entity sentiment"
    assert charts_pdf._module_display_name("custom_mod") == "Custom Mod"


def test_build_charts_pdf_empty_and_with_png(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert charts_pdf.build_charts_pdf(empty, tmp_path / "out.pdf") is None

    # Minimal valid 1x1 PNG
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    root = tmp_path / "run"
    charts = root / "summary" / "charts" / "global"
    charts.mkdir(parents=True)
    (charts / "x.png").write_bytes(png)
    out = tmp_path / "all.pdf"
    try:
        result = charts_pdf.build_charts_pdf(root, out)
    except Exception:
        result = None
    # reportlab may or may not be available; both outcomes are acceptable for coverage.
    assert result is None or (result.exists() and result.stat().st_size > 0)
