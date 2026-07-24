"""Profile adapter round-trip for semantic_similarity."""

from __future__ import annotations

from transcriptx.core.config.profile_target_adapter import ProfileTargetAdapter
from transcriptx.core.config.gui_support import PROFILE_TARGET_CONTRACTS
from transcriptx.core.config.registry import build_registry
from transcriptx.core.utils.config import TranscriptXConfig


def test_profile_target_payload_roundtrip_semantic_v2() -> None:
    cfg = TranscriptXConfig()
    cfg.analysis.semantic_similarity.self_similarity_threshold = 0.81
    cfg.analysis.semantic_similarity.batch_size = 32
    adapter = ProfileTargetAdapter(
        contract=PROFILE_TARGET_CONTRACTS["semantic_similarity"]
    )
    obj = adapter.get_target_config_obj(cfg)
    assert obj is not None
    assert obj.self_similarity_threshold == 0.81
    assert obj.batch_size == 32


def test_profile_guided_fields_exist_in_registry() -> None:
    reg = build_registry()
    guided = PROFILE_TARGET_CONTRACTS["semantic_similarity"].edit_support.guided_fields
    prefix = "analysis.semantic_similarity."
    for field in guided:
        key = f"{prefix}{field}"
        assert key in reg, key
