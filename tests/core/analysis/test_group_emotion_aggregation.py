"""Regression tests for group emotion aggregation (lexical v2 nested stats).

Live group finalize failed with::

    TypeError: unsupported operand type(s) for +: 'float' and 'dict'

when ``aggregate_emotion_group`` treated lexical-v2 ``speaker_stats`` values as
flat score maps. Production stats look like::

    {
      "assignment_counts": {...},   # dict — must not be summed as a score
      "emotion_scores": {"joy": 0.1, ...},
      "tokens_considered": 10,
      "joy": 0.1,  # flat compat copies may also be present
      ...
    }
"""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.aggregation.emotion import (
    _emotion_score_map,
    aggregate_emotion_group,
)
from transcriptx.core.analysis.aggregation.registry import build_registry
from transcriptx.core.analysis.aggregation.schema import (
    validate_session_rows,
    validate_speaker_rows,
)
from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap

PLUTCHIK = (
    "anger",
    "anticipation",
    "disgust",
    "fear",
    "joy",
    "sadness",
    "surprise",
    "trust",
)


def _cmap() -> CanonicalSpeakerMap:
    return CanonicalSpeakerMap(
        transcript_to_speakers={
            "/x/a.json": {"Alice": 1, "Bob": 2},
            "/x/b.json": {"Alice": 1, "Bob": 2},
        },
        canonical_to_display={1: "Alice", 2: "Bob"},
        transcript_to_display={
            "/x/a.json": {"Alice": "Alice", "Bob": "Bob"},
            "/x/b.json": {"Alice": "Alice", "Bob": "Bob"},
        },
    )


def _ts() -> TranscriptSet:
    return TranscriptSet.create(["/x/a.json", "/x/b.json"], name="G", key="gk")


def _lexical_v2_speaker_profile(scores: dict[str, float], *, tokens: int = 10) -> dict:
    """Match emotion module lexical-v2 speaker_stats entry shape (key order matters)."""
    # assignment_counts first — this is what triggered float+dict on the old path.
    profile: dict = {
        "assignment_counts": {k: int(v * 10) for k, v in scores.items()},
        "emotion_scores": dict(scores),
        "valence_assignment_counts": {"positive": 7, "negative": 3},
        "valence_scores": {"positive": 0.7, "negative": 0.3},
        "tokens_considered": tokens,
        "matched_occurrences": 5,
        "mean_coverage": 0.2,
        "zero_hit_segments": 1,
        "no_hit_rate": 0.1,
    }
    # Flat compat copies (also emitted by the module via **normalize_profile).
    profile.update(scores)
    return profile


def _lexical_v2_global(scores: dict[str, float]) -> dict:
    return {
        "assignment_counts": {k: int(v * 10) for k, v in scores.items()},
        "emotion_scores": dict(scores),
        "valence_scores": {"positive": 0.8, "negative": 0.2},
        "tokens_considered": 100,
        "matched_occurrences": 20,
        "mean_coverage": 0.15,
        "zero_hit_segments": 2,
        "no_hit_rate": 0.05,
        **scores,
    }


def _member(
    path: str,
    key: str,
    order: int,
    *,
    alice: dict[str, float],
    bob: dict[str, float],
    global_scores: dict[str, float],
) -> PerTranscriptResult:
    return PerTranscriptResult(
        transcript_path=path,
        transcript_key=key,
        run_id=f"r{order}",
        order_index=order,
        output_dir=f"out/{order}",
        module_results={
            "emotion": {
                "payload": {
                    "semantics_version": "emotion_lexical_v2",
                    "speaker_stats": {
                        "Alice": _lexical_v2_speaker_profile(alice),
                        "Bob": _lexical_v2_speaker_profile(bob),
                    },
                    "global_stats": _lexical_v2_global(global_scores),
                }
            }
        },
    )


@pytest.mark.unit
def test_emotion_score_map_prefers_nested_emotion_scores() -> None:
    mapped = _emotion_score_map(
        {
            "assignment_counts": {"joy": 3},
            "emotion_scores": {"joy": 0.25, "trust": 0.75},
            "tokens_considered": 12,
            "joy": 0.25,
        }
    )
    assert mapped == {"joy": 0.25, "trust": 0.75}
    assert all(isinstance(v, float) for v in mapped.values())


@pytest.mark.unit
def test_emotion_score_map_flat_legacy_payload() -> None:
    assert _emotion_score_map({"joy": 0.4, "sad": 0.6}) == {"joy": 0.4, "sad": 0.6}


@pytest.mark.unit
def test_emotion_score_map_ignores_non_numeric_and_bool() -> None:
    assert _emotion_score_map({"joy": 0.5, "flag": True, "note": "x"}) == {"joy": 0.5}
    assert _emotion_score_map(None) == {}
    assert _emotion_score_map("bad") == {}


@pytest.mark.unit
def test_naive_sum_of_lexical_v2_profile_raises_float_plus_dict() -> None:
    """Guard: the pre-fix loop over raw speaker_stats.items() must keep failing."""
    profile = _lexical_v2_speaker_profile({k: 1.0 / len(PLUTCHIK) for k in PLUTCHIK})
    totals: dict[str, float] = {}
    with pytest.raises(TypeError, match="float.*dict|dict.*float"):
        for emotion, value in profile.items():
            totals[emotion] = totals.get(emotion, 0.0) + value


@pytest.mark.unit
def test_aggregate_emotion_group_lexical_v2_two_members_no_typeerror() -> None:
    base = {k: 0.0 for k in PLUTCHIK}
    alice_a = {**base, "joy": 0.5, "trust": 0.5}
    bob_a = {**base, "anger": 0.2, "fear": 0.8}
    global_a = {**base, "joy": 0.4, "trust": 0.6}
    alice_b = {**base, "joy": 0.3, "trust": 0.7}
    bob_b = {**base, "anger": 0.4, "fear": 0.6}
    global_b = {**base, "joy": 0.2, "trust": 0.8}

    results = [
        _member("/x/a.json", "a", 0, alice=alice_a, bob=bob_a, global_scores=global_a),
        _member("/x/b.json", "b", 1, alice=alice_b, bob=bob_b, global_scores=global_b),
    ]
    outcome = aggregate_emotion_group(results, _cmap(), _ts())
    assert outcome is not None

    by_name = {r["display_name"]: r for r in outcome["speaker_rows"]}
    assert set(by_name) == {"Alice", "Bob"}
    # Unweighted mean across the two appearances.
    assert by_name["Alice"]["emotion_scores"]["joy"] == pytest.approx(0.4)
    assert by_name["Alice"]["emotion_scores"]["trust"] == pytest.approx(0.6)
    assert by_name["Bob"]["emotion_scores"]["anger"] == pytest.approx(0.3)

    pooled = outcome["emotion_pooled"]["emotion_scores"]
    assert pooled["joy"] == pytest.approx(0.3)
    assert pooled["trust"] == pytest.approx(0.7)
    # Nested metadata keys must never leak into pooled/speaker score maps.
    for scores in [pooled, *(r["emotion_scores"] for r in outcome["speaker_rows"])]:
        assert "assignment_counts" not in scores
        assert "emotion_scores" not in scores
        assert "tokens_considered" not in scores
        assert all(isinstance(v, float) for v in scores.values())

    ok_sessions, _ = validate_session_rows(outcome["session_rows"])
    ok_speakers, _ = validate_speaker_rows(outcome["speaker_rows"])
    assert ok_sessions and ok_speakers


@pytest.mark.unit
def test_registry_emotion_aggregate_fn_accepts_lexical_v2() -> None:
    """Same payload through the registry entry finalize uses."""
    entry = next(e for e in build_registry() if e.agg_id == "emotion")
    base = {k: 0.0 for k in PLUTCHIK}
    scores = {**base, "joy": 0.6, "trust": 0.4}
    results = [
        _member(
            "/x/a.json",
            "a",
            0,
            alice=scores,
            bob=scores,
            global_scores=scores,
        )
    ]
    outcome = entry.aggregate_fn(results, _cmap(), _ts())
    assert outcome is not None
    assert outcome["emotion_pooled"]["emotion_scores"]["joy"] == pytest.approx(0.6)
