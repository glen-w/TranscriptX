"""Preset validation and resolve rules for semantic_similarity."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.semantic_similarity.config_resolve import (
    SemanticStrictAdvancedInputsError,
    resolve_semantic_similarity_runtime,
)
from transcriptx.core.utils.config import TranscriptXConfig


def test_unknown_preset_field_raises() -> None:
    cfg = TranscriptXConfig()
    profiles = dict(cfg.analysis.semantic_similarity_profiles)
    profiles["bad"] = {"not_a_field": 1}
    cfg.analysis.semantic_similarity_profiles = profiles
    cfg.analysis.active_semantic_similarity_profile = "bad"
    with pytest.raises(ValueError):
        resolve_semantic_similarity_runtime(cfg.analysis, modules_in_run=set())


def test_balanced_preset_overlays_mode_from_analysis_mode() -> None:
    cfg = TranscriptXConfig()
    cfg.analysis.active_semantic_similarity_profile = "balanced"
    cfg.analysis.analysis_mode = "full"
    resolved, _diag = resolve_semantic_similarity_runtime(
        cfg.analysis,
        modules_in_run={"sentiment", "emotion", "acts"},
    )
    assert resolved.mode == "advanced"
    cfg.analysis.analysis_mode = "quick"
    resolved2, _ = resolve_semantic_similarity_runtime(
        cfg.analysis,
        modules_in_run={"sentiment", "emotion", "acts"},
    )
    assert resolved2.mode == "basic"


def test_strict_advanced_blocks_when_missing() -> None:
    cfg = TranscriptXConfig()
    cfg.analysis.semantic_similarity.mode = "advanced"
    cfg.analysis.semantic_similarity.strict_advanced_inputs = True
    cfg.analysis.active_semantic_similarity_profile = "deep"
    with pytest.raises(SemanticStrictAdvancedInputsError):
        resolve_semantic_similarity_runtime(cfg.analysis, modules_in_run=set())
