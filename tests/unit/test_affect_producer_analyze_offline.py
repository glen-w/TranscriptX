"""Offline producer analyze paths with mocked HF classifiers (no Hub)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from transcriptx.core.analysis.contextual_emotion import ContextualEmotionAnalysis
from transcriptx.core.analysis.fine_grained_emotion import FineGrainedEmotionAnalysis
from transcriptx.core.analysis.hf_text_classification.profiles import (
    CONTEXTUAL_HARTMANN_V1,
    FINE_GRAINED_GOEMOTIONS_V1,
)
from transcriptx.core.analysis.hf_text_classification.runtime import (
    LoadedClassifier,
    ScoreResult,
)


def _loaded(profile) -> LoadedClassifier:
    return LoadedClassifier(
        profile=profile,
        model=MagicMock(),
        tokenizer=MagicMock(),
        device="cpu",
        device_class="cpu",
        dtype="float32",
        cache_key="k",
        effective_max_length=64,
        resolved_label_map_hash="hash",
        resolved_id2label={0: "anger", 1: "joy", 2: "neutral"},
    )


@pytest.mark.unit
def test_contextual_analyze_success_with_mocked_scorer(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTX_CACHE_ROOT", str(tmp_path / "cache"))
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            contextual_emotion=SimpleNamespace(
                profile_id=CONTEXTUAL_HARTMANN_V1.profile_id,
                confidence_threshold=0.3,
                batch_size=8,
            )
        )
    )
    segs = [
        {
            "id": "1",
            "speaker": "Alice",
            "text": "I am delighted",
            "start": 0.0,
            "end": 1.0,
        },
        {
            "id": "2",
            "speaker": "Bob",
            "text": "I am furious",
            "start": 1.0,
            "end": 2.0,
        },
    ]
    scores = [
        ScoreResult(
            scores={
                "anger": 0.05,
                "disgust": 0.02,
                "fear": 0.03,
                "joy": 0.80,
                "neutral": 0.05,
                "sadness": 0.03,
                "surprise": 0.02,
            },
            truncated=False,
            omitted_token_count_lower_bound=0,
            device_class="cpu",
            dtype="float32",
        ),
        ScoreResult(
            scores={
                "anger": 0.82,
                "disgust": 0.04,
                "fear": 0.03,
                "joy": 0.03,
                "neutral": 0.04,
                "sadness": 0.02,
                "surprise": 0.02,
            },
            truncated=False,
            omitted_token_count_lower_bound=0,
            device_class="cpu",
            dtype="float32",
        ),
    ]
    with (
        patch(
            "transcriptx.core.utils.config.get_config",
            return_value=cfg,
        ),
        patch(
            "transcriptx.core.analysis.contextual_emotion.load_classifier",
            return_value=_loaded(CONTEXTUAL_HARTMANN_V1),
        ),
        patch(
            "transcriptx.core.analysis.contextual_emotion.score_texts",
            return_value=scores,
        ),
        patch(
            "transcriptx.core.analysis.contextual_emotion.library_versions",
            return_value={"transformers_version": "0", "torch_version": "0"},
        ),
    ):
        out = ContextualEmotionAnalysis().analyze(segs)
    assert out["run_status"] == "complete"
    assert out["usable_output"] is True
    assert out["segments_scored"] == 2
    assert out.get("_pending_projections")
    assert segs[0].get("contextual_emotion_label") is None
    from transcriptx.core.analysis.contextual_emotion.projections import (
        apply_contextual_projection,
    )
    from transcriptx.core.analysis.emotion_family.persist import (
        apply_pending_projections,
    )

    apply_pending_projections(out, apply_one=apply_contextual_projection)
    assert segs[0].get("contextual_emotion_label") == "joy"
    assert segs[1].get("contextual_emotion_label") == "anger"
    assert segs[0].get("context_emotion_source") == "contextual_emotion"


@pytest.mark.unit
def test_fine_grained_analyze_success_with_mocked_scorer(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCRIPTX_CACHE_ROOT", str(tmp_path / "cache"))
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(
            fine_grained_emotion=SimpleNamespace(
                profile_id=FINE_GRAINED_GOEMOTIONS_V1.profile_id,
                label_threshold=0.3,
                max_labels_per_segment=3,
                batch_size=8,
            )
        )
    )
    segs = [
        {
            "id": "1",
            "speaker": "Alice",
            "text": "I am grateful and joyful",
            "start": 0.0,
            "end": 1.0,
        }
    ]
    full = {lab: 0.01 for lab in FINE_GRAINED_GOEMOTIONS_V1.labels}
    full["joy"] = 0.80
    full["gratitude"] = 0.70
    full["anger"] = 0.01
    full["neutral"] = 0.05
    # sigmoid: no sum-to-1 requirement
    scores = [
        ScoreResult(
            scores=full,
            truncated=False,
            omitted_token_count_lower_bound=0,
            device_class="cpu",
            dtype="float32",
        )
    ]
    with (
        patch(
            "transcriptx.core.utils.config.get_config",
            return_value=cfg,
        ),
        patch(
            "transcriptx.core.analysis.fine_grained_emotion.load_classifier",
            return_value=_loaded(FINE_GRAINED_GOEMOTIONS_V1),
        ),
        patch(
            "transcriptx.core.analysis.fine_grained_emotion.score_texts",
            return_value=scores,
        ),
        patch(
            "transcriptx.core.analysis.fine_grained_emotion.library_versions",
            return_value={"transformers_version": "0", "torch_version": "0"},
        ),
    ):
        out = FineGrainedEmotionAnalysis().analyze(segs)
    assert out["run_status"] == "complete"
    assert out["usable_output"] is True
    assert out["segments_scored"] == 1
    assert out.get("_pending_projections")
    assert segs[0].get("fine_grained_emotion_labels") is None
    from transcriptx.core.analysis.fine_grained_emotion.projections import (
        apply_fine_grained_projection,
    )
    from transcriptx.core.analysis.emotion_family.persist import (
        apply_pending_projections,
    )

    apply_pending_projections(out, apply_one=apply_fine_grained_projection)
    assert "joy" in (segs[0].get("fine_grained_emotion_labels") or [])
