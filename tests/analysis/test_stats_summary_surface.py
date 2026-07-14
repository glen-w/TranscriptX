"""Targeted regression tests for stats summary surface."""

from __future__ import annotations

from transcriptx.core.analysis.stats import summary as stats_summary


def _speaker_stats() -> list[tuple]:
    return [
        (61.0, "Alice", 120, 8, 0.05, 15.0),
        (49.0, "Bob", 80, 7, 0.03, 11.4),
    ]


def _module_data() -> dict:
    return {
        "acts": {"Alice": {"statement": 3}},
        "interactions": {
            "speaker_summary": [
                {
                    "speaker": "Alice",
                    "interruptions_initiated": 1,
                    "interruptions_received": 2,
                    "responses_initiated": 3,
                    "responses_received": 4,
                    "dominance_score": 0.7,
                }
            ]
        },
        "emotion": {"speaker_emotions": {"Alice": {"joy": 0.8, "calm": 0.2}}},
        "ner": {"Alice": {"ProjectX": 2}},
        "entity_sentiment": {"Alice": {"ProjectX": {"sentiment_score": 0.4}}},
        "conversation_loops": {
            "loops": [{"speakers": ["Alice", "Bob"], "topic": "Roadmap"}]
        },
        "contagion": {
            "contagion_events": [
                {
                    "source_speaker": "Alice",
                    "target_speaker": "Bob",
                    "emotion": "joy",
                    "strength": 0.5,
                }
            ]
        },
    }


def test_summary_module_imports_cleanly() -> None:
    assert hasattr(stats_summary, "create_comprehensive_summary")
    assert not hasattr(stats_summary, "generate_enhanced_html_summary")
    assert not hasattr(stats_summary, "generate_summary_stats")


def test_create_comprehensive_summary_headings_and_order() -> None:
    text = stats_summary.create_comprehensive_summary(
        transcript_dir="/tmp",
        base_name="sample",
        speaker_stats=_speaker_stats(),
        sentiment_summary={
            "Alice": {"compound": 0.3, "pos": 0.4, "neu": 0.5, "neg": 0.1},
            "Bob": {"compound": -0.1, "pos": 0.2, "neu": 0.6, "neg": 0.2},
        },
        module_data=_module_data(),
    )
    expected_headings = [
        "🎯 BASIC STATISTICS",
        "😊 SENTIMENT ANALYSIS",
        "🗣️ DIALOGUE ACTS",
        "🤝 SPEAKER INTERACTIONS",
        "😄 EMOTION ANALYSIS",
        "🏷️ NAMED ENTITIES",
        "🎯 ENTITY SENTIMENT ANALYSIS",
        "🔄 CONVERSATION LOOPS",
        "😊 EMOTIONAL CONTAGION",
        "💡 KEY INSIGHTS",
    ]
    pos = [text.find(h) for h in expected_headings]
    assert all(p != -1 for p in pos)
    assert pos == sorted(pos)


def test_create_comprehensive_summary_header_and_key_insights_invariants() -> None:
    text = stats_summary.create_comprehensive_summary(
        transcript_dir="/tmp",
        base_name="sample",
        speaker_stats=_speaker_stats(),
        sentiment_summary={
            "Alice": {"compound": 0.3, "pos": 0.4, "neu": 0.5, "neg": 0.1},
            "Bob": {"compound": -0.1, "pos": 0.2, "neu": 0.6, "neg": 0.2},
        },
        module_data=_module_data(),
    )
    lines = text.splitlines()
    assert lines[0] == "📊 COMPREHENSIVE ANALYSIS SUMMARY: sample"
    assert lines[1] == "=" * 60
    assert "• Most talkative speaker: Alice (120 words)" in text
    assert "• Most dominant speaker: Alice (score: 0.700)" in text
    assert "📁 Detailed outputs available in module-specific directories:" in text


def test_create_comprehensive_summary_filtering_and_fallbacks() -> None:
    text = stats_summary.create_comprehensive_summary(
        transcript_dir="/tmp",
        base_name="sample",
        speaker_stats=[(10.0, "Alice", 5, 1, 0.0, 5.0)],
        sentiment_summary={
            "SPEAKER_00": {"compound": 0.9, "pos": 1.0, "neu": 0.0, "neg": 0.0}
        },
        module_data={},
    )
    assert "SPEAKER_00                 " not in text
    assert "Most positive speaker: SPEAKER_00" not in text
    assert "Most negative speaker: SPEAKER_00" not in text
    assert "No data available for this section." in text
    assert "🗣️ DIALOGUE ACTS" in text
    assert "🤝 SPEAKER INTERACTIONS" in text
    assert "😄 EMOTION ANALYSIS" in text


def test_create_comprehensive_summary_respects_alias_filtering() -> None:
    text = stats_summary.create_comprehensive_summary(
        transcript_dir="/tmp",
        base_name="sample",
        speaker_stats=[],
        sentiment_summary={
            "AliasName": {"compound": 0.8, "pos": 0.8, "neu": 0.1, "neg": 0.1}
        },
        module_data={"acts": {"AliasName": {"statement": 2}}},
        ignored_ids={"SPEAKER_42"},
        speaker_key_aliases={"AliasName": "SPEAKER_42"},
    )
    assert "AliasName" not in text
    assert "No data available for this section." in text
