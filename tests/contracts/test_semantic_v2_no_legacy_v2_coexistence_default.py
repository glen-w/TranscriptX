"""Default module list uses semantic_similarity v2 id; no legacy advanced twin."""

from __future__ import annotations

from transcriptx.core.pipeline.module_registry import get_default_modules


def test_default_plan_has_v2_not_legacy_semantic() -> None:
    mods = get_default_modules(include_legacy=False)
    # Post-epoch: the sole semantic module id is ``semantic_similarity`` (v2 impl).
    assert "semantic_similarity" in mods
    assert "semantic_similarity_advanced" not in mods
    assert "semantic_similarity_v2" not in mods
