"""ContextualEmotionAnalysis.analyze branches beyond the happy path.

Offline: the HF classifier and scorer are mocked, as in
``test_affect_producer_analyze_offline.py``. Covers preflight failure, invalid
segment ids, empty text, invalid scores, abstention below threshold, and
unavailable caches.
"""

from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.contextual_emotion import ContextualEmotionAnalysis
from transcriptx.core.analysis.contextual_emotion.projections import (
    apply_contextual_projection,
)
from transcriptx.core.analysis.emotion_family.persist import (
    apply_pending_projections,
)
from transcriptx.core.analysis.hf_text_classification.profiles import (
    CONTEXTUAL_HARTMANN_V1,
)
from transcriptx.core.analysis.hf_text_classification.runtime import (
    LoadedClassifier,
    ScoreResult,
)

pytestmark = pytest.mark.unit

_MOD = "transcriptx.core.analysis.contextual_emotion"
_LABELS = ("anger", "disgust", "fear", "joy", "neutral", "sadness", "surprise")


def _loaded() -> LoadedClassifier:
    return LoadedClassifier(
        profile=CONTEXTUAL_HARTMANN_V1,
        model=MagicMock(),
        tokenizer=MagicMock(),
        device="cpu",
        device_class="cpu",
        dtype="float32",
        cache_key="k",
        effective_max_length=64,
        resolved_label_map_hash="hash",
        resolved_id2label=dict(enumerate(_LABELS)),
    )


def _score(top: str, top_score: float, labels=_LABELS) -> ScoreResult:
    rest = (1.0 - top_score) / (len(labels) - 1)
    return ScoreResult(
        scores={lab: (top_score if lab == top else rest) for lab in labels},
        truncated=False,
        omitted_token_count_lower_bound=0,
        device_class="cpu",
        dtype="float32",
    )


def _seg(sid: str, text: str, speaker: str = "Alice") -> dict:
    return {"segment_id": sid, "speaker": speaker, "text": text, "start": 0.0}


def _run(segments, *, scores=None, load_error=None, threshold=0.45, extra=()):
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            contextual_emotion=SimpleNamespace(
                profile_id=CONTEXTUAL_HARTMANN_V1.profile_id,
                confidence_threshold=threshold,
                batch_size=8,
            )
        )
    )
    load = (
        patch(f"{_MOD}.load_classifier", side_effect=load_error)
        if load_error
        else patch(f"{_MOD}.load_classifier", return_value=_loaded())
    )
    with ExitStack() as stack:
        stack.enter_context(
            patch("transcriptx.core.utils.config.get_config", return_value=cfg)
        )
        stack.enter_context(load)
        stack.enter_context(
            patch(f"{_MOD}.score_texts", return_value=list(scores or []))
        )
        stack.enter_context(
            patch(
                f"{_MOD}.library_versions",
                return_value={"transformers_version": "0", "torch_version": "0"},
            )
        )
        for ctx in extra:
            stack.enter_context(ctx)
        return ContextualEmotionAnalysis().analyze(segments)


@pytest.fixture(autouse=True)
def _cache_root(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTX_CACHE_ROOT", str(tmp_path / "cache"))


def test_preflight_failure_skips_and_clears_projection() -> None:
    seg = _seg("a", "I am delighted")
    seg["contextual_emotion_label"] = "stale"
    out = _run([seg], load_error=RuntimeError("model unavailable"))
    assert out["run_status"] == "skipped"
    assert out["usable_output"] is False
    assert out["preflight_reason"] == "preflight_failed"
    assert "model unavailable" in out["preflight_details"]["message"]
    assert "contextual_emotion_label" not in seg


def test_duplicate_segment_ids_fail_closed() -> None:
    out = _run([_seg("dup", "one"), _seg("dup", "two")])
    assert out["run_status"] == "failed"
    assert out["usable_output"] is False
    assert out["preflight_reason"] == "invalid_segment_ids"


def test_empty_text_segment_is_recorded_not_scored() -> None:
    segs = [_seg("a", "I am delighted"), _seg("b", "")]
    out = _run(segs, scores=[_score("joy", 0.9)])
    assert out["segments_scored"] == 1
    assert out["segments_empty"] == 1
    apply_pending_projections(out, apply_one=apply_contextual_projection)
    assert segs[0]["contextual_emotion_label"] == "joy"
    assert segs[1]["contextual_emotion_label"] == ""


def test_invalid_scores_mark_segment_failed() -> None:
    wrong_labels = ("happy", "sad")
    out = _run(
        [_seg("a", "I am delighted")], scores=[_score("happy", 0.9, wrong_labels)]
    )
    assert out["segments_scored"] == 0
    assert out["segments_failed"] == 1
    rows = out["_canonical_rows"]
    assert rows[0]["evaluation_state"] == "failed"
    assert rows[0]["fail_reason"] == "invalid_or_missing_scores"


def test_low_confidence_abstains_without_label() -> None:
    segs = [_seg("a", "Hmm, maybe")]
    out = _run(segs, scores=[_score("joy", 0.30)], threshold=0.45)
    assert out["segments_scored"] == 1
    assert out["outcome_counts"].get("abstained") == 1
    assert not out["label_counts"]
    apply_pending_projections(out, apply_one=apply_contextual_projection)
    assert segs[0]["contextual_emotion_analytical_outcome"] == "abstained"
    assert segs[0]["contextual_emotion_label"] == ""


def test_neutral_top_label_is_neutral_outcome() -> None:
    out = _run([_seg("a", "The meeting is at noon")], scores=[_score("neutral", 0.9)])
    assert out["outcome_counts"].get("neutral") == 1


def test_unavailable_caches_still_produce_results() -> None:
    broken = RuntimeError("read-only cache root")
    out = _run(
        [_seg("a", "I am furious")],
        scores=[_score("anger", 0.9)],
        extra=(
            patch(f"{_MOD}.InferenceCacheStore", side_effect=broken),
            patch(f"{_MOD}.AggregationCacheStore", side_effect=broken),
        ),
    )
    assert out["run_status"] == "complete"
    assert out["label_counts"] == {"anger": 1}
