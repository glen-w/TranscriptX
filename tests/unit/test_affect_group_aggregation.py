"""Group aggregation gates for contextual / fine-grained emotion."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.analysis.aggregation.contextual_emotion import (
    aggregate_contextual_emotion_group,
    aggregate_fine_grained_emotion_group,
)


def _ptr(path: str, module_id: str, payload: dict):
    return SimpleNamespace(
        transcript_path=path,
        run_id="run-1",
        module_results={module_id: {"payload": payload}},
        order_index=0,
    )


def _poolable(fingerprint: str, **extra):
    payload = {
        "run_status": "complete",
        "usable_output": True,
        "segments_scored": 3,
        "compatibility_fingerprint": fingerprint,
        "primary_rates": {"neutral_rate": 0.2, "labeled_rate": 0.8},
        "release_channel": "experimental",
        "profile_id": "p1",
    }
    payload.update(extra)
    return payload


@pytest.mark.unit
def test_group_skips_zero_scored_complete():
    results = [
        _ptr(
            "a.json",
            "contextual_emotion",
            _poolable("fp1", usable_output=False, segments_scored=0),
        )
    ]
    transcript_set = SimpleNamespace()
    out = aggregate_contextual_emotion_group(results, SimpleNamespace(), transcript_set)
    assert out is None


@pytest.mark.unit
def test_group_separates_incompatible_fingerprints(monkeypatch):
    # session_row_from_result needs real-ish transcript_set; stub the helper.
    monkeypatch.setattr(
        "transcriptx.core.analysis.aggregation.contextual_emotion.session_row_from_result",
        lambda result, transcript_set, **extra: {
            "order_index": getattr(result, "order_index", 0),
            "transcript_path": result.transcript_path,
            **extra,
        },
    )
    results = [
        _ptr("a.json", "contextual_emotion", _poolable("fp-a")),
        _ptr(
            "b.json",
            "contextual_emotion",
            _poolable("fp-b", primary_rates={"neutral_rate": 0.5}),
        ),
    ]
    out = aggregate_contextual_emotion_group(
        results, SimpleNamespace(), SimpleNamespace()
    )
    assert out is not None
    assert set(out["pooled_by_fingerprint"]) == {"fp-a", "fp-b"}
    # Multiple cohorts → no blended top-level rates.
    assert out["primary_rates_pooled"] == {}


@pytest.mark.unit
def test_fine_grained_single_cohort_pools(monkeypatch):
    monkeypatch.setattr(
        "transcriptx.core.analysis.aggregation.contextual_emotion.session_row_from_result",
        lambda result, transcript_set, **extra: {
            "order_index": 0,
            "transcript_path": result.transcript_path,
            **extra,
        },
    )
    results = [
        _ptr(
            "a.json",
            "fine_grained_emotion",
            _poolable("fp1", primary_rates={"no_label_rate": 0.1, "mixed_rate": 0.2}),
        ),
        _ptr(
            "b.json",
            "fine_grained_emotion",
            _poolable("fp1", primary_rates={"no_label_rate": 0.3, "mixed_rate": 0.4}),
        ),
    ]
    out = aggregate_fine_grained_emotion_group(
        results, SimpleNamespace(), SimpleNamespace()
    )
    assert out is not None
    assert out["primary_rates_pooled"]["no_label_rate"] == pytest.approx(0.2)
    assert out["primary_rates_pooled"]["mixed_rate"] == pytest.approx(0.3)
