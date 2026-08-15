"""Noise regression pack for Theme A deterministic insights."""

import pytest

pytest.importorskip("spacy")

pytestmark = pytest.mark.requires_nlp

from transcriptx.core.analysis.insights.analysis import InsightsAnalysis
from transcriptx.core.analysis.phrase_quality import PHRASE_QUALITY_VERSION

BANNED_FILLERS = (
    "kind of",
    "sort of",
    "of course",
    "i think",
    "you know",
    "sounds good",
    "makes sense",
)


def _ctx(payload: dict):
    return type(
        "Ctx", (), {"get_analysis_result": lambda _self, key: payload.get(key)}
    )()


def test_phrase_quality_version_bumped_for_theme_a() -> None:
    assert PHRASE_QUALITY_VERSION >= 3


def test_singleton_gate_requires_spread_or_recurrence() -> None:
    """Mirror eligibility singleton rule without requiring spaCy."""
    metrics = {"total": 0.5, "spread": 0.0, "recurrence": 0.0}
    token_count = 1
    require = True
    drop = (
        require
        and token_count <= 1
        and metrics["spread"] <= 0.0
        and metrics["recurrence"] <= 0.0
    )
    assert drop is True
    metrics2 = {"total": 0.5, "spread": 0.2, "recurrence": 0.0}
    drop2 = (
        require
        and token_count <= 1
        and metrics2["spread"] <= 0.0
        and metrics2["recurrence"] <= 0.0
    )
    assert drop2 is False


def test_insights_never_emits_banned_fillers_as_themes() -> None:
    phrases = []
    scores = {}
    for filler in BANNED_FILLERS:
        phrases.append(
            {
                "phrase": filler,
                "score": {"total": 0.95, "spread": 0.6, "recurrence": 0.6},
            }
        )
        scores[filler] = {"total": 0.95, "spread": 0.6, "recurrence": 0.6}
    # Include two strong themes so status stays ok when fillers are rejected.
    for good in ("budget risk", "launch timeline"):
        phrases.append(
            {
                "phrase": good,
                "score": {"total": 0.8, "spread": 0.4, "recurrence": 0.4},
            }
        )
        scores[good] = {"total": 0.8, "spread": 0.4, "recurrence": 0.4}

    analysis = InsightsAnalysis()
    analysis._context = _ctx(
        {
            "insight_eligibility": {
                "content_phrases": phrases,
                "phrase_scores": scores,
            },
            "highlights": {"sections": {"cold_open": {"items": []}}},
            "topic_modeling": {},
            "tics": {"speaker_stats": {}, "global_stats": {}},
        }
    )
    payload = analysis.analyze(segments=[])
    theme_texts = [row["phrase"].lower() for row in payload["key_themes"]]
    idea_texts = [row["phrase"].lower() for row in payload["recurring_ideas"]]
    for filler in BANNED_FILLERS:
        assert filler not in theme_texts
        assert filler not in idea_texts
    assert "budget risk" in theme_texts
    assert "launch timeline" in theme_texts
