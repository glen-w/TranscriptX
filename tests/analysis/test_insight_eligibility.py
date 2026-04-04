from transcriptx.core.analysis.insight_eligibility.content_filter import (
    filter_segments_for_insights,
)
from transcriptx.core.analysis.insight_eligibility.windowing import (
    build_rolling_windows,
    build_speaker_blocks,
)
from transcriptx.core.analysis.insight_eligibility.phrase_extraction import (
    extract_content_phrases,
)
from transcriptx.core.analysis.topic_modeling.utils import (
    generate_topic_labels,
    topic_rejected,
)


def test_content_filter_keeps_domain_verbs_and_drops_discourse_verbs() -> None:
    segments = [
        {
            "segment_index": 0,
            "speaker": "Alice",
            "start": 0.0,
            "end": 1.0,
            "text": "I think we build forecasting models for grid planning",
        }
    ]
    filtered, tic_mask, tic_mask_sources = filter_segments_for_insights(segments)
    assert filtered
    assert "think" in tic_mask
    assert "from_verbal_tics_stoplist" in tic_mask_sources
    assert "from_discourse_stoplist" in tic_mask_sources
    tokens = filtered[0].content_tokens
    assert "build" in tokens
    assert "think" not in tokens


def test_windowing_uses_rolling_windows_as_canonical_docs() -> None:
    segments = [
        {
            "segment_index": idx,
            "speaker": "Alice" if idx % 2 == 0 else "Bob",
            "start": float(idx),
            "end": float(idx) + 0.5,
            "text": f"battery storage planning segment {idx}",
        }
        for idx in range(6)
    ]
    filtered, _mask, _sources = filter_segments_for_insights(segments)
    windows = build_rolling_windows(filtered, window_size=3, stride=2)
    blocks = build_speaker_blocks(filtered)
    assert windows
    assert blocks
    assert len(windows[0]["segment_indexes"]) <= 3
    assert all("text" in window and window["text"] for window in windows)


def test_phrase_extraction_rejects_phrase_level_tics() -> None:
    segments = [
        {
            "segment_index": 0,
            "speaker": "Alice",
            "start": 0.0,
            "end": 1.0,
            "text": "I think climate change policy and battery storage matter",
        },
        {
            "segment_index": 1,
            "speaker": "Bob",
            "start": 1.0,
            "end": 2.0,
            "text": "climate change policy affects battery storage planning",
        },
    ]
    filtered, tic_mask, _sources = filter_segments_for_insights(segments)
    windows = build_rolling_windows(filtered, window_size=2, stride=1)
    blocks = build_speaker_blocks(filtered)
    rows, _scores = extract_content_phrases(
        filtered,
        tic_mask=tic_mask,
        windows=windows,
        speaker_blocks=blocks,
        min_frequency=1,
    )
    phrases = [row["phrase"] for row in rows]
    assert all("think" not in phrase for phrase in phrases)


def test_topic_rejection_and_label_generation() -> None:
    banned_terms = {"think", "know", "mean"}
    assert topic_rejected(["think", "know", "battery"], banned_terms=banned_terms)
    assert not topic_rejected(["battery", "storage", "grid"], banned_terms=banned_terms)

    label = generate_topic_labels(
        ["battery", "batteries", "storage", "stored"],
        [0.9, 0.8, 0.7, 0.6],
        banned_terms=set(),
    )
    assert label == "Battery Storage"


def test_phrase_boundary_is_not_substring_match() -> None:
    banned_terms = {"plan"}
    assert topic_rejected(["plan", "roadmap", "delivery"], banned_terms=banned_terms)
    assert not topic_rejected(
        ["planet", "roadmap", "delivery"], banned_terms=banned_terms
    )


def test_phrase_extraction_contract_rejects_pronouns_shards_and_fillers() -> None:
    segments = [
        {
            "segment_index": 0,
            "speaker": "A",
            "start": 0.0,
            "end": 1.0,
            "text": "I mean we kind of need to decide the next step",
        },
        {
            "segment_index": 1,
            "speaker": "B",
            "start": 1.0,
            "end": 2.0,
            "text": "You know we should decide and delay launch if needed",
        },
        {
            "segment_index": 2,
            "speaker": "A",
            "start": 2.0,
            "end": 3.0,
            "text": "he'd said we'd do it, but we need a decision",
        },
    ]
    filtered, tic_mask, _sources = filter_segments_for_insights(segments)
    windows = build_rolling_windows(filtered, window_size=2, stride=1)
    blocks = build_speaker_blocks(filtered)
    rows, _scores = extract_content_phrases(
        filtered,
        tic_mask=tic_mask,
        windows=windows,
        speaker_blocks=blocks,
        min_frequency=1,
    )
    phrases = {str(row["phrase"]).lower() for row in rows}

    for banned in {"i", "it", "we", "you", "he", "d", "kind of", "i mean", "you know"}:
        assert banned not in phrases
    assert any("decision" in phrase for phrase in phrases) or any(
        "decide" in phrase for phrase in phrases
    )
    assert any("next step" in phrase for phrase in phrases)


def test_phrase_extraction_keeps_non_aux_verb_led_phrases() -> None:
    segments = [
        {
            "segment_index": 0,
            "speaker": "A",
            "start": 0.0,
            "end": 1.0,
            "text": "We decide now and agree on timeline",
        },
        {
            "segment_index": 1,
            "speaker": "B",
            "start": 1.0,
            "end": 2.0,
            "text": "If risk grows we delay launch and rethink pricing",
        },
    ]
    filtered, tic_mask, _sources = filter_segments_for_insights(segments)
    windows = build_rolling_windows(filtered, window_size=2, stride=1)
    blocks = build_speaker_blocks(filtered)
    rows, _scores = extract_content_phrases(
        filtered,
        tic_mask=tic_mask,
        windows=windows,
        speaker_blocks=blocks,
        min_frequency=1,
    )
    phrases = {str(row["phrase"]).lower() for row in rows}

    assert any("decide" in phrase for phrase in phrases)
    assert any("agree" in phrase for phrase in phrases)
    assert any("delay" in phrase and "launch" in phrase for phrase in phrases) or any(
        "delay" in phrase for phrase in phrases
    )
    assert any("rethink" in phrase for phrase in phrases)


def test_phrase_extraction_filters_cross_lingual_fragments_without_content_head() -> (
    None
):
    segments = [
        {
            "segment_index": 0,
            "speaker": "A",
            "start": 0.0,
            "end": 1.0,
            "text": "de lo de lo",
        },
        {
            "segment_index": 1,
            "speaker": "B",
            "start": 1.0,
            "end": 2.0,
            "text": "we decide launch timeline",
        },
    ]
    filtered, tic_mask, _sources = filter_segments_for_insights(segments)
    windows = build_rolling_windows(filtered, window_size=2, stride=1)
    blocks = build_speaker_blocks(filtered)
    rows, _scores = extract_content_phrases(
        filtered,
        tic_mask=tic_mask,
        windows=windows,
        speaker_blocks=blocks,
        min_frequency=1,
    )
    phrases = {str(row["phrase"]).lower() for row in rows}
    assert "de" not in phrases
    assert "lo" not in phrases
    assert "de lo" not in phrases
    assert "launch timeline" in phrases or "timeline" in phrases


def test_contrast_semantic_vs_conversational_signal_separation() -> None:
    segments = [
        {
            "segment_index": 0,
            "speaker": "A",
            "start": 0.0,
            "end": 1.0,
            "text": "We need to make a decision about the next step.",
        },
        {
            "segment_index": 1,
            "speaker": "B",
            "start": 1.0,
            "end": 2.0,
            "text": "I mean we kind of need to decide.",
        },
    ]
    filtered, tic_mask, _sources = filter_segments_for_insights(segments)
    windows = build_rolling_windows(filtered, window_size=2, stride=1)
    blocks = build_speaker_blocks(filtered)
    rows, _scores = extract_content_phrases(
        filtered,
        tic_mask=tic_mask,
        windows=windows,
        speaker_blocks=blocks,
        min_frequency=1,
    )
    phrases = {str(row["phrase"]).lower() for row in rows}
    assert any("decision" in phrase for phrase in phrases)
    assert "next step" in phrases or "step" in phrases
    assert "i" not in phrases
    assert "we" not in phrases
    assert "kind of" not in phrases
    assert "i mean" not in phrases
