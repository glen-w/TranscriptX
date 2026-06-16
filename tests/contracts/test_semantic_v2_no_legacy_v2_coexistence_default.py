"""Default module list does not include legacy semantic modules when include_legacy is False."""

from __future__ import annotations

from transcriptx.core.pipeline.module_registry import get_default_modules


def test_default_plan_has_v2_not_legacy_semantic() -> None:
    mods = get_default_modules(include_legacy=False)
    assert "semantic_similarity_v2" in mods
    assert "semantic_similarity" not in mods
    assert "semantic_similarity_advanced" not in mods
