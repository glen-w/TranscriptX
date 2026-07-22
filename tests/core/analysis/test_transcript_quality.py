"""Unit tests for ASR confidence / transcript_quality."""

from __future__ import annotations

from transcriptx.core.analysis.transcript_quality.aggregation import (
    aggregate_transcript_quality,
)
from transcriptx.core.analysis.transcript_quality.analyze import compute_asr_confidence
from transcriptx.core.analysis.transcript_quality.provenance import build_provenance
from transcriptx.core.analysis.transcript_quality.scores import (
    classify_score,
    normalize_word_dict,
)
from transcriptx.core.analysis.transcript_quality.spans import (
    SpanBuildConfig,
    build_spans_and_clusters,
)
from transcriptx.core.analysis.transcript_quality.words import extract_word_records
from transcriptx.core.domain.canonical_transcript import TranscriptCapabilities


def _word(text, start, end, score=None, speaker="A", **extra):
    w = {"word": text, "start": start, "end": end, "speaker": speaker}
    if score is not None:
        w["score"] = score
    w.update(extra)
    return w


def _seg(words, speaker="A", start=None, end=None, text=None):
    starts = [w["start"] for w in words]
    ends = [w["end"] for w in words]
    return {
        "start": start if start is not None else min(starts),
        "end": end if end is not None else max(ends),
        "speaker": speaker,
        "text": text or " ".join(w["word"] for w in words),
        "words": words,
    }


class TestScorePolicy:
    def test_accept_unit_interval(self):
        assert classify_score(0.0).accepted == 0.0
        assert classify_score(1.0).accepted == 1.0
        assert classify_score(0.42).accepted == 0.42

    def test_omit_out_of_range_without_clamp(self):
        cleaned, verdict = normalize_word_dict({"word": "x", "score": 1.5})
        assert "score" not in cleaned
        assert verdict.out_of_range is True
        assert verdict.accepted is None

    def test_invalid_score(self):
        cleaned, verdict = normalize_word_dict({"word": "x", "score": "nope"})
        assert "score" not in cleaned
        assert verdict.invalid is True

    def test_invalid_includes_infinity(self):
        cleaned, verdict = normalize_word_dict({"word": "x", "score": float("inf")})
        assert "score" not in cleaned
        assert verdict.invalid is True
        assert verdict.out_of_range is False


class TestStatusSemantics:
    def test_absent_when_no_scores(self):
        segs = [_seg([_word("hi", 0, 0.5), _word("there", 0.5, 1.0)])]
        result = compute_asr_confidence(segs, cfg=SpanBuildConfig())
        asr = result["asr_confidence"]
        assert asr["status"] == "absent"
        assert asr["scored_word_count"] == 0
        assert asr["spans"] == []

    def test_present_when_all_eligible_scored(self):
        segs = [
            _seg(
                [
                    _word("hi", 0, 0.5, 0.9),
                    _word("there", 0.5, 1.0, 0.8),
                ]
            )
        ]
        asr = compute_asr_confidence(segs, cfg=SpanBuildConfig())["asr_confidence"]
        assert asr["status"] == "present"
        assert asr["coverage_ratio"] == 1.0

    def test_partial_and_diagnostics(self):
        segs = [
            _seg(
                [
                    _word("a", 0, 0.2, 0.9),
                    _word("b", 0.2, 0.4),  # missing
                    _word("c", 0.4, 0.6, 1.7),  # out of range
                    _word("d", 0.6, 0.8, "bad"),  # invalid
                ]
            )
        ]
        asr = compute_asr_confidence(segs, cfg=SpanBuildConfig())["asr_confidence"]
        assert asr["status"] == "partial"
        assert asr["scored_word_count"] == 1
        assert asr["missing_score_count"] == 1
        assert asr["out_of_range_score_count"] == 1
        assert asr["invalid_score_count"] == 1


class TestSpans:
    def test_breaks_on_speaker_change(self):
        words = [
            _word("low1", 0.0, 0.2, 0.1, speaker="A"),
            _word("low2", 0.2, 0.4, 0.1, speaker="B"),
        ]
        segs = [_seg(words)]
        records, _ = extract_word_records(segs)
        out = build_spans_and_clusters(records, SpanBuildConfig(max_spans=10))
        assert out["spans_total_count"] == 2

    def test_breaks_on_missing_score_in_stream(self):
        words = [
            _word("low1", 0.0, 0.2, 0.1),
            _word("mid", 0.2, 0.4),  # missing score breaks
            _word("low2", 0.4, 0.6, 0.1),
        ]
        records, _ = extract_word_records([_seg(words)])
        out = build_spans_and_clusters(records, SpanBuildConfig())
        assert out["spans_total_count"] == 2

    def test_breaks_on_timestamp_reversal(self):
        from transcriptx.core.analysis.transcript_quality.spans import _should_break_span

        segs = [
            {
                "start": 1.0,
                "end": 1.2,
                "speaker": "A",
                "text": "a",
                "words": [_word("a", 1.0, 1.2, 0.1, speaker="A")],
            },
            {
                "start": 0.2,
                "end": 0.4,
                "speaker": "A",
                "text": "b",
                "words": [_word("b", 0.2, 0.4, 0.1, speaker="A")],
            },
        ]
        records, _ = extract_word_records(segs)
        # After sort: earlier start first. Force reverse check on helper.
        later = records[1]
        earlier = records[0]
        assert _should_break_span(later, earlier, cfg=SpanBuildConfig()) is True

    def test_breaks_on_segment_discontinuity(self):
        segs = [
            _seg([_word("a", 0.0, 0.2, 0.1)]),
            {"start": 10.0, "end": 10.2, "speaker": "A", "text": "skip", "words": []},
            _seg([_word("b", 10.0, 10.2, 0.1)]),
        ]
        records, _ = extract_word_records(segs)
        assert [r.segment_index for r in records] == [0, 2]
        out = build_spans_and_clusters(records, SpanBuildConfig(max_gap_seconds=100))
        assert out["spans_total_count"] == 2

    def test_overlapping_low_words_remain_contiguous(self):
        words = [
            _word("a", 0.0, 1.0, 0.1),
            _word("b", 0.5, 1.5, 0.2),  # overlap
        ]
        records, _ = extract_word_records([_seg(words)])
        out = build_spans_and_clusters(records, SpanBuildConfig())
        assert out["spans_total_count"] == 1
        assert out["spans"][0]["word_count"] == 2

    def test_caps_expose_totals(self):
        words = [_word(f"w{i}", float(i), float(i) + 0.2, 0.1) for i in range(5)]
        # force separate spans via large gaps
        for i, w in enumerate(words):
            w["start"] = float(i) * 10
            w["end"] = w["start"] + 0.2
        records, _ = extract_word_records([_seg(words)])
        out = build_spans_and_clusters(
            records, SpanBuildConfig(max_gap_seconds=0.5, max_spans=2, max_clusters=1)
        )
        assert out["spans_total_count"] == 5
        assert out["spans_emitted_count"] == 2
        assert out["clusters_total_count"] >= 1
        assert out["clusters_emitted_count"] == 1

    def test_playback_payload_present(self):
        segs = [_seg([_word("low", 1.0, 1.5, 0.2)])]
        asr = compute_asr_confidence(segs, cfg=SpanBuildConfig())["asr_confidence"]
        span = asr["spans"][0]
        assert span["playback"]["start"] == 1.0
        assert span["playback"]["segment_index"] == 0


class TestCapabilities:
    def test_has_word_confidence(self):
        caps = TranscriptCapabilities.from_segments(
            [_seg([_word("x", 0, 0.5, 0.7)])]
        )
        assert caps.has_word_confidence is True
        caps2 = TranscriptCapabilities.from_segments(
            [_seg([_word("x", 0, 0.5)])]
        )
        assert caps2.has_word_confidence is False


class TestAggregation:
    def test_weighted_pool_and_incompatible_exclusion(self):
        from types import SimpleNamespace

        def _result(order, payload):
            return SimpleNamespace(
                order_index=order,
                transcript_path=f"/t{order}.json",
                transcript_key=f"tk{order}",
                output_dir=f"/out{order}",
                module_results={"transcript_quality": payload},
                session_id=f"s{order}",
                run_id=f"r{order}",
            )

        p_a = build_provenance(import_adapter="whisperx", asr_engine="whisperx")
        p_b = build_provenance(import_adapter="other", asr_engine="other")

        def _payload(prov, eligible, scored, mean, low):
            return {
                "provenance": prov,
                "asr_confidence": {
                    "status": "present" if scored == eligible else "partial",
                    "eligible_word_count": eligible,
                    "scored_word_count": scored,
                    "coverage_ratio": scored / eligible if eligible else None,
                    "mean_score": mean,
                    "low_score_word_count": low,
                    "low_score_ratio": low / scored if scored else None,
                },
            }

        results = [
            _result(0, _payload(p_a, 100, 100, 0.8, 10)),
            _result(1, _payload(p_a, 50, 50, 0.4, 20)),
            _result(2, _payload(p_b, 200, 200, 0.99, 0)),
        ]
        transcript_set = SimpleNamespace(members=[], metadata={})
        out = aggregate_transcript_quality(results, None, transcript_set)
        assert out is not None
        pooled = out["transcript_quality_pooled"]
        assert pooled["member_count"] == 3
        assert pooled["pooled_member_count"] == 2
        assert pooled["incompatible_member_count"] == 1
        # coverage = 150/150
        assert pooled["coverage"] == 1.0
        # weighted mean = (0.8*100 + 0.4*50) / 150 = 100/150
        assert abs(pooled["mean_score"] - (100 / 150)) < 1e-9
        # low ratio = 30/150
        assert abs(pooled["low_score_ratio"] - 0.2) < 1e-9
