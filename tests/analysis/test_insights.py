"""Tests for insights."""

from transcriptx.core.analysis.insights.analysis import InsightsAnalysis


def _ctx(payload: dict):
    return type(
        "Ctx", (), {"get_analysis_result": lambda _self, key: payload.get(key)}
    )()


def test_insights_payload_excludes_rejected_topics_debug() -> None:
    analysis = InsightsAnalysis()
    context_payload = {
        "insight_eligibility": {
            "content_phrases": [
                {
                    "phrase": "battery storage",
                    "score": {
                        "total": 0.8,
                        "spread": 0.4,
                        "recurrence": 0.3,
                    },
                },
                {
                    "phrase": "grid capacity",
                    "score": {
                        "total": 0.75,
                        "spread": 0.35,
                        "recurrence": 0.25,
                    },
                },
            ],
            "phrase_scores": {
                "battery storage": {
                    "total": 0.8,
                    "recurrence": 0.2,
                    "spread": 0.4,
                },
                "grid capacity": {
                    "total": 0.75,
                    "recurrence": 0.25,
                    "spread": 0.35,
                },
            },
        },
        "highlights": {"sections": {"cold_open": {"items": []}}},
        "topic_modeling": {"rejected_topics": {"lda": [{"topic_id": 1}]}},
        "tics": {"speaker_stats": {}, "global_stats": {}},
    }
    analysis._context = _ctx(context_payload)
    payload = analysis.analyze(segments=[])
    assert "rejected_topics_debug" not in payload
    assert payload["schema_version"] == 3
    assert payload["status"] == "ok"


def test_insights_ranking_prefers_semantic_phrases_over_conversational_fillers() -> (
    None
):
    analysis = InsightsAnalysis()
    context_payload = {
        "insight_eligibility": {
            "content_phrases": [
                {
                    "phrase": "budget risk",
                    "score": {"total": 0.82, "spread": 0.4, "recurrence": 0.5},
                },
                {
                    "phrase": "delivery timeline",
                    "score": {"total": 0.8, "spread": 0.35, "recurrence": 0.45},
                },
                {"phrase": "i", "score": {"total": 0.21, "spread": 0.1, "recurrence": 0.2}},
                {"phrase": "we", "score": {"total": 0.19, "spread": 0.1, "recurrence": 0.1}},
                {
                    "phrase": "kind of",
                    "score": {"total": 0.9, "spread": 0.5, "recurrence": 0.5},
                },
            ],
            "phrase_scores": {
                "budget risk": {"total": 0.82, "recurrence": 0.5, "spread": 0.4},
                "delivery timeline": {
                    "total": 0.8,
                    "recurrence": 0.45,
                    "spread": 0.35,
                },
                "i": {"total": 0.21, "recurrence": 0.2, "spread": 0.1},
                "we": {"total": 0.19, "recurrence": 0.1, "spread": 0.1},
                "kind of": {"total": 0.9, "recurrence": 0.5, "spread": 0.5},
            },
        },
        "highlights": {"sections": {"cold_open": {"items": []}}},
        "topic_modeling": {},
        "tics": {"speaker_stats": {}, "global_stats": {}},
    }
    analysis._context = _ctx(context_payload)
    payload = analysis.analyze(segments=[])
    key_themes = [row["phrase"] for row in payload["key_themes"]]
    assert "budget risk" in key_themes
    assert "delivery timeline" in key_themes
    assert "i" not in key_themes
    assert "we" not in key_themes
    assert "kind of" not in key_themes
    assert key_themes.index("budget risk") < key_themes.index("delivery timeline")


def test_insights_abstains_when_only_weak_phrases() -> None:
    analysis = InsightsAnalysis()
    context_payload = {
        "insight_eligibility": {
            "content_phrases": [
                {"phrase": "i", "score": {"total": 0.5, "spread": 0.2, "recurrence": 0.2}},
                {
                    "phrase": "kind of",
                    "score": {"total": 0.6, "spread": 0.3, "recurrence": 0.3},
                },
            ],
            "phrase_scores": {
                "i": {"total": 0.5, "recurrence": 0.2, "spread": 0.2},
                "kind of": {"total": 0.6, "recurrence": 0.3, "spread": 0.3},
            },
        },
        "highlights": {"sections": {"cold_open": {"items": []}}},
        "topic_modeling": {},
        "tics": {"speaker_stats": {}, "global_stats": {}},
    }
    analysis._context = _ctx(context_payload)
    payload = analysis.analyze(segments=[])
    assert payload["status"] == "insufficient_signal"
    assert payload["key_themes"] == []
    assert payload["recurring_ideas"] == []


def test_insights_attaches_evidence_and_confidence() -> None:
    analysis = InsightsAnalysis()
    context_payload = {
        "insight_eligibility": {
            "content_phrases": [
                {
                    "phrase": "budget risk",
                    "score": {"total": 0.8, "spread": 0.4, "recurrence": 0.5},
                },
                {
                    "phrase": "hiring plan",
                    "score": {"total": 0.7, "spread": 0.3, "recurrence": 0.4},
                },
            ],
            "phrase_scores": {
                "budget risk": {"total": 0.8, "recurrence": 0.5, "spread": 0.4},
                "hiring plan": {"total": 0.7, "recurrence": 0.4, "spread": 0.3},
            },
        },
        "highlights": {
            "transcript_key": "t1",
            "themes": [
                {
                    "label": "budget risk",
                    "quote_ids": ["q:t1:1", "q:t1:2"],
                    "is_unthemed": False,
                }
            ],
            "sections": {"cold_open": {"items": []}},
        },
        "topic_modeling": {
            "topics": [{"label": "budget planning", "words": [("budget", 0.4)]}]
        },
        "tics": {"speaker_stats": {}, "global_stats": {}},
    }
    analysis._context = _ctx(context_payload)
    payload = analysis.analyze(segments=[])
    assert payload["status"] == "ok"
    themes = {row["phrase"]: row for row in payload["key_themes"]}
    assert "budget risk" in themes
    assert themes["budget risk"]["evidence_quote_ids"] == ["q:t1:1", "q:t1:2"]
    assert themes["budget risk"]["confidence"] in {"high", "medium", "low"}
    assert themes["budget risk"]["topic_corroborated"] is True
