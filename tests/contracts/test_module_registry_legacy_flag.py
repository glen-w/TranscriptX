"""Registry legacy flag and default module selection for semantic modules."""

from __future__ import annotations

from transcriptx.core.pipeline.module_registry import (
    get_default_modules,
    get_module_info,
)


def test_semantic_modules_marked_legacy() -> None:
    assert get_module_info("semantic_similarity") is not None
    assert get_module_info("semantic_similarity").legacy is True
    assert get_module_info("semantic_similarity_advanced").legacy is True
    assert get_module_info("semantic_similarity_v2").legacy is False


def test_default_modules_exclude_legacy_semantic_when_include_legacy_false() -> None:
    mods = get_default_modules(include_legacy=False)
    assert "semantic_similarity" not in mods
    assert "semantic_similarity_advanced" not in mods
    assert "semantic_similarity_v2" in mods


def test_default_modules_include_legacy_semantic_when_include_legacy_true() -> None:
    mods = get_default_modules(include_legacy=True)
    assert "semantic_similarity" in mods
    assert "semantic_similarity_advanced" in mods
    assert "semantic_similarity_v2" in mods
