"""Tests for insights."""

from transcriptx.core.analysis.insights.analysis import InsightsAnalysis


def test_insights_payload_excludes_rejected_topics_debug() -> None:
    analysis = InsightsAnalysis()
    context_payload = {
        "insight_eligibility": {
            "content_phrases": [{"phrase": "battery storage", "score": {"total": 0.8}}],
            "phrase_scores": {"battery storage": {"total": 0.8, "recurrence": 0.2}},
        },
        "highlights": {"sections": {"cold_open": {"items": []}}},
        "topic_modeling": {"rejected_topics": {"lda": [{"topic_id": 1}]}},
        "tics": {"speaker_stats": {}, "global_stats": {}},
    }
    analysis._context = type(
        "Ctx", (), {"get_analysis_result": lambda _self, key: context_payload.get(key)}
    )()
    payload = analysis.analyze(segments=[])
    assert "rejected_topics_debug" not in payload


def test_insights_ranking_prefers_semantic_phrases_over_conversational_fillers() -> (
    None
):
    analysis = InsightsAnalysis()
    context_payload = {
        "insight_eligibility": {
            "content_phrases": [
                {"phrase": "decision", "score": {"total": 0.82}},
                {"phrase": "next step", "score": {"total": 0.8}},
                {"phrase": "i", "score": {"total": 0.21}},
                {"phrase": "we", "score": {"total": 0.19}},
            ],
            "phrase_scores": {
                "decision": {"total": 0.82, "recurrence": 0.5},
                "next step": {"total": 0.8, "recurrence": 0.45},
                "i": {"total": 0.21, "recurrence": 0.2},
                "we": {"total": 0.19, "recurrence": 0.1},
            },
        },
        "highlights": {"sections": {"cold_open": {"items": []}}},
        "topic_modeling": {},
        "tics": {"speaker_stats": {}, "global_stats": {}},
    }
    analysis._context = type(
        "Ctx", (), {"get_analysis_result": lambda _self, key: context_payload.get(key)}
    )()
    payload = analysis.analyze(segments=[])
    key_themes = [row["phrase"] for row in payload["key_themes"]]
    assert key_themes.index("decision") < key_themes.index("i")
    assert key_themes.index("next step") < key_themes.index("we")
