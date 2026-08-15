"""Corpus-level acceptance checks for key-theme phrase quality."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("spacy")

pytestmark = pytest.mark.requires_nlp

from transcriptx.core.analysis.highlights.core import (
    SegmentLite,
    _compute_emblematic_phrases,
)
from transcriptx.core.analysis.phrase_quality.analyser import (
    analyse_phrase,
    annotations_from_surfaces,
)
from transcriptx.core.analysis.phrase_quality.types import (
    DISCOURSE_FORMULA,
    LIGHT_VERB_CONSTRUCTION,
)
from transcriptx.core.analysis.summary.core import compute_summary
from transcriptx.core.utils.config.analysis import HighlightsConfig, SummaryConfig
from transcriptx.core.utils.nlp_utils import build_tic_mask

BANNED = {
    "of course",
    "for example",
    "need to",
    "going to",
    "we need",
    "kind of",
    "i mean",
}


def _seg(idx: int, speaker: str, text: str) -> SegmentLite:
    return SegmentLite(
        segment_key=f"idx:corp:{idx}",
        segment_db_id=None,
        segment_uuid=None,
        segment_index=idx,
        speaker_display=speaker,
        speaker_id=idx,
        start=float(idx),
        end=float(idx) + 1.0,
        text=text,
    )


def _synthetic_corpus() -> list[SegmentLite]:
    lines = [
        ("Alice", "Of course we need to discuss budget risk and timeline."),
        ("Bob", "For example the budget risk affects launch planning."),
        ("Alice", "We are going to mitigate budget risk this quarter."),
        ("Bob", "Need assessment of the launch planning timeline."),
        ("Alice", "Course design and example dataset reviews are ready."),
        ("Bob", "Going concern accounting and war crimes investigation came up."),
        ("Alice", "Point estimate for budget risk looks solid."),
        ("Bob", "We need assessment? No — need assessment of pricing."),
        ("Alice", "Budget risk and launch planning keep returning."),
        ("Bob", "Timeline and pricing need assessment before we ship."),
    ]
    # Repeat to satisfy min frequency thresholds.
    segs: list[SegmentLite] = []
    idx = 0
    for _ in range(3):
        for speaker, text in lines:
            segs.append(_seg(idx, speaker, text))
            idx += 1
    return segs


def test_corpus_acceptance_banned_formulas_and_populated_slots() -> None:
    segments = _synthetic_corpus()
    cfg = HighlightsConfig()
    started = time.perf_counter()
    phrases = _compute_emblematic_phrases(segments, cfg, build_tic_mask())
    elapsed = time.perf_counter() - started
    assert elapsed < 30.0, f"emblematic mining too slow: {elapsed:.2f}s"

    phrase_texts = {str(p.get("phrase") or "").lower() for p in phrases}
    assert phrase_texts.isdisjoint(BANNED)

    highlights = {
        "transcript_key": "corpus",
        "sections": {
            "emblematic_phrases": {"phrases": phrases},
            "conflict_points": {"events": []},
            "cold_open": {"items": []},
        },
        "themes": [],
    }
    summary = compute_summary(highlights, segments, SummaryConfig())
    bullets = summary["key_themes"]["bullets"]
    bullet_texts = [str(b.get("text") or "").lower() for b in bullets]
    assert bullet_texts
    assert set(bullet_texts).isdisjoint(BANNED)
    # Prefer topical content from the corpus.
    joined = " ".join(bullet_texts)
    assert any(
        term in joined
        for term in ("budget", "risk", "launch", "planning", "timeline", "pricing")
    )

    # Rejection reason histogram on known junk.
    reasons = []
    for junk in BANNED:
        result = analyse_phrase(annotations_from_surfaces(junk.split()))
        reasons.append(result.hard_reject_reason)
    assert DISCOURSE_FORMULA in reasons or LIGHT_VERB_CONSTRUCTION in reasons

    # Duplicate-theme rate among selected bullets should be zero after diversity fill.
    assert len(bullet_texts) == len(set(bullet_texts))
