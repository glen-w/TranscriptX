"""Targeted regression tests for stats summary surface."""

from __future__ import annotations

import warnings

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
    assert hasattr(stats_summary, "generate_enhanced_html_summary")
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


def test_generate_enhanced_html_summary_retained_with_deprecation(tmp_path) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        stats_summary.generate_enhanced_html_summary(
            transcript_dir=str(tmp_path),
            base_name="sample",
            module_data={},
            speaker_map={},
        )
    assert any(item.category is DeprecationWarning for item in caught)
    assert (tmp_path / "sample_comprehensive_summary.html").is_file()


def test_generate_enhanced_html_summary_collects_classified_assets(tmp_path) -> None:
    (tmp_path / "emotion_plot.png").write_text("img", encoding="utf-8")
    (tmp_path / "location_entities.png").write_text("img", encoding="utf-8")
    (tmp_path / "location_map.html").write_text("<html></html>", encoding="utf-8")

    stats_summary.generate_enhanced_html_summary(
        transcript_dir=str(tmp_path),
        base_name="sample",
        module_data={},
        speaker_map={},
    )
    html = (tmp_path / "sample_comprehensive_summary.html").read_text(encoding="utf-8")
    assert "Emotion Detection" in html
    assert "location_map.html" in html


def test_create_enhanced_html_content_minimal_compatibility_smoke() -> None:
    html = stats_summary.create_enhanced_html_content(
        base_name='sample"><script>alert(1)</script>',
        timestamp="2026-01-01 12:00:00",
        module_images={
            "sentiment": ["sentiment_chart.png"],
            "other": ["misc_chart.png"],
        },
        module_html_files={"sentiment": ["sentiment_map.html"]},
        module_data={"sentiment": "High-level narrative"},
        speaker_map={"SPEAKER_01": "Alice"},
    )
    assert "Comprehensive Analysis Summary" in html
    assert "Table of Contents" in html
    assert "Sentiment Analysis" in html
    assert "Other Visualizations" in html
    assert "sentiment_chart.png" in html
    assert "sentiment_map.html" in html
    assert "sample&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_create_enhanced_html_content_skips_structured_or_long_module_summary() -> None:
    html = stats_summary.create_enhanced_html_content(
        base_name="sample",
        timestamp="2026-01-01 12:00:00",
        module_images={"sentiment": ["sentiment_chart.png"]},
        module_html_files={},
        module_data={"sentiment": {"structured": "payload"}, "emotion": "x" * 600},
        speaker_map={"SPEAKER_01": "Alice"},
    )
    assert '<h5><i class="fas fa-clipboard-list me-2"></i>Summary</h5>' not in html
