"""Profile adapter round-trip for semantic_similarity_v2."""

from __future__ import annotations

from transcriptx.core.config.profile_target_adapter import ProfileTargetAdapter
from transcriptx.core.config.gui_support import PROFILE_TARGET_CONTRACTS
from transcriptx.core.utils.config import TranscriptXConfig


def test_profile_target_payload_roundtrip_semantic_v2() -> None:
    cfg = TranscriptXConfig()
    cfg.analysis.semantic_similarity_v2.self_similarity_threshold = 0.81
    cfg.analysis.semantic_similarity_v2.batch_size = 32
    adapter = ProfileTargetAdapter(
        contract=PROFILE_TARGET_CONTRACTS["semantic_similarity_v2"]
    )
    obj = adapter.get_target_config_obj(cfg)
    assert obj is not None
    assert obj.self_similarity_threshold == 0.81
    assert obj.batch_size == 32
