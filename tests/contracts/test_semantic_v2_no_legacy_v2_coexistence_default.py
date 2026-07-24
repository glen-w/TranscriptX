"""Default module list uses ``semantic_similarity`` only."""

from __future__ import annotations

from transcriptx.core.pipeline.module_registry import get_default_modules


def test_default_plan_has_semantic_similarity_only() -> None:
    mods = get_default_modules(include_legacy=False)
    assert "semantic_similarity" in mods
    assert "semantic_similarity_advanced" not in mods
    assert "semantic_similarity_v2" not in mods
