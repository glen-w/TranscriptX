"""Direct unit coverage for exemplar helper ranking/merge paths."""

from __future__ import annotations

from transcriptx.core.analysis.exemplars import (
    SegmentRecord,
    _apply_length_prior,
    _dedupe_segments,
    _length_prior,
    _merge_adjacent,
    _normalize_text,
    _percentile,
    _rank_normalize,
    _tokenize,
    _word_count,
    compute_speaker_exemplars,
)
from transcriptx.core.utils.config import SpeakerExemplarsConfig


def _seg(idx: int, text: str, *, speaker: str = "s1") -> SegmentRecord:
    return SegmentRecord(
        segment_id=f"id-{idx}",
        segment_index=idx,
        speaker_id=speaker,
        text=text,
        word_count=None,
        start_time=float(idx),
        end_time=float(idx) + 1.0,
    )


def test_exemplar_helper_edges() -> None:
    assert _tokenize("Hello, world!") == ["hello", "world"]
    assert _normalize_text("  Hi!! There  ") == "hi there"
    assert _word_count("one two three") == 3
    assert _percentile([], 50) == 0.0
    assert _percentile([1.0, 2.0, 3.0], 50) == 2.0
    assert _length_prior(5, 5.0, 0.0) == 1.0
    assert 0.0 < _length_prior(5, 10.0, 2.0) < 1.0


def test_merge_adjacent_and_dedupe() -> None:
    cfg = SpeakerExemplarsConfig(
        merge_adjacent=True,
        max_words=20,
        dedupe=True,
        near_dedupe=True,
        near_dedupe_threshold=0.8,
        near_dedupe_max_checks=10,
    )
    merged = _merge_adjacent(
        [
            _seg(0, "we should"),
            _seg(1, "continue talking"),
            _seg(2, "Stop here."),
            _seg(3, "Next sentence"),
        ],
        cfg,
    )
    assert len(merged) < 4
    assert any("continue talking" in s.text for s in merged)

    deduped = _dedupe_segments(
        [_seg(0, "yeah"), _seg(1, "yeah!"), _seg(2, "totally different words here")],
        cfg,
    )
    assert len(deduped) <= 2


def test_rank_normalize_and_length_prior_application() -> None:
    segs = [_seg(i, f"word{i} alpha beta") for i in range(5)]
    ranks = _rank_normalize(segs, [0.1, 0.5, 0.5, 0.9, 0.2])
    assert ranks is not None
    assert max(ranks) == 1.0
    assert _rank_normalize(segs[:3], [1.0, 2.0, 3.0]) is None

    cfg = SpeakerExemplarsConfig(
        length_prior_enabled=True, length_prior_center=3.0, length_prior_sigma=1.0
    )
    weighted = _apply_length_prior(segs, [1.0] * 5, cfg)
    assert all(w > 0 for w in weighted)
    assert (
        _apply_length_prior(
            segs, [1.0] * 5, SpeakerExemplarsConfig(length_prior_enabled=False)
        )
        == [1.0] * 5
    )


def test_compute_with_merge_and_distinctive() -> None:
    cfg = SpeakerExemplarsConfig(
        count=3,
        min_words=1,
        max_words=30,
        merge_adjacent=True,
        dedupe=True,
        methods_enabled={
            "unique": True,
            "tfidf_within_speaker": True,
            "distinctive_vs_others": True,
        },
        weights={
            "unique": 1.0,
            "tfidf_within_speaker": 1.0,
            "distinctive_vs_others": 1.0,
        },
        distinctive_min_other_segments=2,
        length_prior_enabled=True,
    )
    speaker = [_seg(i, f"budget risk planning item {i}") for i in range(6)]
    others = [_seg(100 + i, f"weather chat {i}", speaker="s2") for i in range(4)]
    results = compute_speaker_exemplars(speaker, other_segments=others, config=cfg)
    assert results.combined
    assert results.metadata.get("filtered_count", 0) >= 1
