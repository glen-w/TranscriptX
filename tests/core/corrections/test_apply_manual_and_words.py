"""Apply corrections: manual kind, word sync, per-replacement provenance."""

from __future__ import annotations

from transcriptx.core.corrections.apply import apply_corrections
from transcriptx.core.corrections.models import Candidate, Decision, Occurrence


def _occ(segment_id: str, span, wrong: str) -> Occurrence:
    return Occurrence(
        segment_id=segment_id,
        span=span,
        snippet=wrong,
        occurrence_id=f"{segment_id}:{span[0]}:{span[1]}",
    )


def test_manual_applies_for_unidentified_speaker_without_rule():
    segments = [
        {
            "speaker": "SPEAKER_00",
            "start": 0.0,
            "end": 1.0,
            "text": "hello wrld",
            "words": [
                {"word": "hello", "start": 0.0, "end": 0.4},
                {"word": "wrld", "start": 0.5, "end": 0.9},
            ],
        }
    ]
    # segment_id from resolve uses hash; use apply with known key by matching detect
    from transcriptx.core.corrections.detect import resolve_segment_id

    sid = resolve_segment_id(segments[0], "key", segment_index=0)
    cand = Candidate(
        proposed_wrong="wrld",
        proposed_right="world",
        kind="manual",
        confidence=1.0,
        occurrences=[_occ(sid, (6, 10), "wrld")],
    )
    out, patch = apply_corrections(
        segments,
        [cand],
        "key",
        decisions=[Decision(candidate_id=cand.candidate_id, decision="apply_all")],
    )
    assert out[0]["text"] == "hello world"
    words = out[0]["words"]
    assert words[0]["word"] == "hello"
    assert words[0].get("start") == 0.0
    assert words[1]["word"] == "world"
    assert words[1].get("start") is None  # cleared timing for replaced token


def test_consistency_without_rule_skipped_for_unidentified():
    segments = [
        {
            "speaker": "SPEAKER_00",
            "start": 0.0,
            "end": 1.0,
            "text": "hello wrld",
        }
    ]
    from transcriptx.core.corrections.detect import resolve_segment_id

    sid = resolve_segment_id(segments[0], "key", segment_index=0)
    cand = Candidate(
        proposed_wrong="wrld",
        proposed_right="world",
        kind="consistency",
        confidence=0.5,
        occurrences=[_occ(sid, (6, 10), "wrld")],
    )
    out, _ = apply_corrections(
        segments,
        [cand],
        "key",
        decisions=[Decision(candidate_id=cand.candidate_id, decision="apply_all")],
    )
    assert out[0]["text"] == "hello wrld"


def test_multi_replacement_provenance_per_candidate():
    segments = [
        {
            "speaker": "Alice",
            "start": 0.0,
            "end": 2.0,
            "text": "aaa bbb ccc",
            "words": [
                {"word": "aaa", "start": 0.0, "end": 0.2},
                {"word": "bbb", "start": 0.3, "end": 0.5},
                {"word": "ccc", "start": 0.6, "end": 0.8},
            ],
        }
    ]
    from transcriptx.core.corrections.detect import resolve_segment_id

    sid = resolve_segment_id(segments[0], "key", segment_index=0)
    c1 = Candidate(
        proposed_wrong="aaa",
        proposed_right="AAA",
        kind="manual",
        confidence=1.0,
        occurrences=[_occ(sid, (0, 3), "aaa")],
    )
    c2 = Candidate(
        proposed_wrong="ccc",
        proposed_right="CCC",
        kind="manual",
        confidence=1.0,
        occurrences=[_occ(sid, (8, 11), "ccc")],
    )
    out, patch = apply_corrections(
        segments,
        [c1, c2],
        "key",
        decisions=[
            Decision(candidate_id=c1.candidate_id, decision="apply_all"),
            Decision(candidate_id=c2.candidate_id, decision="apply_all"),
        ],
    )
    assert out[0]["text"] == "AAA bbb CCC"
    applied = [e for e in patch if "replacements" in e and e.get("status") is None]
    assert len(applied) == 1
    reps = applied[0]["replacements"]
    ids = {r["candidate_id"] for r in reps}
    assert c1.candidate_id in ids
    assert c2.candidate_id in ids
    for r in reps:
        assert "occurrence_id" in r
        assert r["kind"] == "manual"
    # Untouched middle word keeps timing
    assert out[0]["words"][1]["word"] == "bbb"
    assert out[0]["words"][1].get("start") == 0.3


def test_word_sync_failsafe_clears_stale_timed_tokens():
    segments = [
        {
            "speaker": "Alice",
            "start": 0.0,
            "end": 1.0,
            "text": "hello world",
            # Misaligned words[] relative to text
            "words": [{"word": "zzz", "start": 9.9, "end": 10.0}],
        }
    ]
    from transcriptx.core.corrections.detect import resolve_segment_id

    sid = resolve_segment_id(segments[0], "key", segment_index=0)
    cand = Candidate(
        proposed_wrong="world",
        proposed_right="earth",
        kind="manual",
        confidence=1.0,
        occurrences=[_occ(sid, (6, 11), "world")],
    )
    out, _ = apply_corrections(
        segments,
        [cand],
        "key",
        decisions=[Decision(candidate_id=cand.candidate_id, decision="apply_all")],
    )
    assert out[0]["text"] == "hello earth"
    assert all(w.get("start") is None for w in out[0]["words"])
    assert [w["word"] for w in out[0]["words"]] == ["hello", "earth"]
