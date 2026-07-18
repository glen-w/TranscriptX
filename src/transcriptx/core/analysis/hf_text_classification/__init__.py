"""Shared Hugging Face text-classification runtime."""

from __future__ import annotations

from transcriptx.core.analysis.hf_text_classification.runtime import (
    LONG_TEXT_POLICY_V1,
    LONG_TEXT_POLICY_V2,
    NUMERICAL_DTYPE_V1,
    LoadedClassifier,
    ModelProfile,
    ScoreResult,
    clear_model_cache,
    device_class_for,
    load_classifier,
    resolve_device,
    score_texts,
)

__all__ = [
    "LONG_TEXT_POLICY_V1",
    "LONG_TEXT_POLICY_V2",
    "NUMERICAL_DTYPE_V1",
    "LoadedClassifier",
    "ModelProfile",
    "ScoreResult",
    "clear_model_cache",
    "device_class_for",
    "load_classifier",
    "resolve_device",
    "score_texts",
]
