from transcriptx.core.analysis.exemplars import SegmentRecord, compute_speaker_exemplars
from transcriptx.core.utils.config import SpeakerExemplarsConfig


def _make_segment(idx: int, text: str) -> SegmentRecord:
    return SegmentRecord(
        segment_id=f"seg-{idx}",
        segment_index=idx,
        speaker_id="speaker-1",
        text=text,
        word_count=None,
        start_time=float(idx),
        end_time=float(idx + 1),
    )


def test_rank_normalization_tiebreaker_order() -> None:
    config = SpeakerExemplarsConfig(
        count=5,
        min_words=1,
        max_words=20,
        merge_adjacent=False,
        methods_enabled={
            "unique": False,
            "tfidf_within_speaker": True,
            "distinctive_vs_others": False,
        },
        weights={"tfidf_within_speaker": 1.0},
    )
    segments = [_make_segment(i, "same text") for i in range(5)]
    results = compute_speaker_exemplars(segments, other_segments=[], config=config)
    ordered_indexes = [item.segment_index for item in results.combined]
    assert ordered_indexes == sorted(ordered_indexes)


def test_weights_renormalize_when_method_unavailable() -> None:
    config = SpeakerExemplarsConfig(
        count=6,
        min_words=1,
        max_words=20,
        merge_adjacent=False,
        methods_enabled={
            "unique": True,
            "tfidf_within_speaker": True,
            "distinctive_vs_others": True,
        },
        weights={
            "unique": 1.0,
            "tfidf_within_speaker": 1.0,
            "distinctive_vs_others": 10.0,
        },
        distinctive_min_other_segments=50,
    )
    segments = [_make_segment(i, f"text {i}") for i in range(6)]
    results = compute_speaker_exemplars(segments, other_segments=[], config=config)
    assert "distinctive_vs_others" not in results.metadata.get("methods_available", [])
    assert any(item.combined_score > 0 for item in results.combined)


def test_near_dedupe_collapses_similar_tokens() -> None:
    config = SpeakerExemplarsConfig(
        count=10,
        min_words=1,
        max_words=20,
        merge_adjacent=False,
        dedupe=True,
        near_dedupe=True,
        near_dedupe_threshold=0.8,
        near_dedupe_max_checks=50,
        methods_enabled={
            "unique": True,
            "tfidf_within_speaker": False,
            "distinctive_vs_others": False,
        },
        weights={"unique": 1.0},
    )
    segments = [
        _make_segment(0, "yeah"),
        _make_segment(1, "yeah!"),
        _make_segment(2, "yeah yeah"),
        _make_segment(3, "ok"),
        _make_segment(4, "ok."),
        _make_segment(5, "ok ok"),
    ]
    results = compute_speaker_exemplars(segments, other_segments=[], config=config)
    assert results.metadata.get("deduped_count") <= 2


def test_caps_enforced_on_large_inputs() -> None:
    config = SpeakerExemplarsConfig(
        count=5,
        min_words=1,
        max_words=10,
        merge_adjacent=False,
        dedupe=False,
        max_segments_considered=200,
        methods_enabled={
            "unique": True,
            "tfidf_within_speaker": False,
            "distinctive_vs_others": False,
        },
        weights={"unique": 1.0},
    )
    segments = [_make_segment(i, "hello world") for i in range(50000)]
    results = compute_speaker_exemplars(segments, other_segments=[], config=config)
    assert results.metadata.get("input_count") == 50000
    assert results.metadata.get("filtered_count") == 200
