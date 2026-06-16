"""Compatibility tests for legacy stats HTML summary helpers."""

from transcriptx.core.analysis.stats.summary_legacy_html import (
    LEGACY_HTML_MODULES_INFO,
    classify_html_module,
    classify_image_module,
)


def test_classify_html_module_routes_expected_names() -> None:
    assert classify_html_module("location_map.html") == "ner"
    assert classify_html_module("emotional_contagion.html") == "contagion"
    assert classify_html_module("misc_dashboard.html") == "other"


def test_classify_image_module_routes_expected_names() -> None:
    assert classify_image_module("speaker_sentiment_timeline.png") == "sentiment"
    assert classify_image_module("emotion_radar.png") == "emotion"
    assert classify_image_module("speaker_emotional_map.png") == "contagion"
    assert classify_image_module("meeting_dominance_plot.png") == "meeting-dominance"
    assert classify_image_module("social_heatmap.png") == "interaction-heatmaps"
    assert (
        classify_image_module("semantic_similarity_matrix.png") == "semantic-similarity"
    )
    assert classify_image_module("speaker_word_cloud.png") == "wordclouds"
    assert classify_image_module("speech_tics_breakdown.png") == "tics"
    assert classify_image_module("topic_keywords.png") == "topic-modeling"
    assert classify_image_module("unknown_plot.png") == "other"


def test_legacy_modules_info_contains_expected_sections() -> None:
    assert "sentiment" in LEGACY_HTML_MODULES_INFO
    assert "contagion" in LEGACY_HTML_MODULES_INFO
    assert "stats" in LEGACY_HTML_MODULES_INFO
