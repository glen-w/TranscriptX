"""Registry: semantic_similarity is the sole non-legacy public module id."""

from __future__ import annotations

from transcriptx.core.pipeline.module_registry import (
    get_default_modules,
    get_module_info,
)


def test_semantic_similarity_is_current_not_legacy() -> None:
    info = get_module_info("semantic_similarity")
    assert info is not None
    assert info.legacy is False
    assert get_module_info("semantic_similarity_advanced") is None
    assert get_module_info("semantic_similarity_v2") is None


def test_default_modules_include_semantic_similarity() -> None:
    mods = get_default_modules(include_legacy=False)
    assert "semantic_similarity" in mods
    assert "semantic_similarity_advanced" not in mods
    assert "semantic_similarity_v2" not in mods
