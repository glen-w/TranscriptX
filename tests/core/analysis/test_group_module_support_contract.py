"""Contracts: every supports_group module is covered by group aggregation."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.aggregation.registry import build_registry
from transcriptx.core.pipeline.module_registry import (
    get_available_modules,
    get_default_modules,
    get_module_info,
)

# Modules covered by a multi-module aggregation selector (no dedicated agg_id).
_COVERED_BY_SELECTOR_ALIAS = {
    "voice_features": "prosody",
    "voice_charts_core": "prosody",
    "prosody_dashboard": "prosody",
    "semantic_similarity_advanced": "semantic_similarity",
    "semantic_similarity_v2": "semantic_similarity",
}


@pytest.mark.unit
def test_supports_group_modules_have_aggregation_coverage() -> None:
    registry = build_registry()
    covered: set[str] = set()
    for entry in registry:
        # Probe selector membership for every available module id.
        for module_id in get_available_modules():
            if entry.selector([module_id]):
                covered.add(module_id)

    missing: list[str] = []
    for module_id in get_available_modules():
        info = get_module_info(module_id)
        assert info is not None
        if not info.supports_group:
            continue
        if module_id in covered:
            continue
        missing.append(module_id)

    assert (
        not missing
    ), "supports_group=true modules missing aggregation coverage: " + ", ".join(
        sorted(missing)
    )


@pytest.mark.unit
def test_supports_group_false_filtered_from_group_defaults() -> None:
    unsupported = [
        module_id
        for module_id in get_available_modules()
        if (info := get_module_info(module_id)) is not None and not info.supports_group
    ]
    assert unsupported
    defaults = get_default_modules(for_group=True)
    leaked = [module_id for module_id in unsupported if module_id in defaults]
    assert not leaked, f"unsupported modules in group defaults: {leaked}"


@pytest.mark.unit
def test_alias_modules_map_to_expected_agg_ids() -> None:
    registry = {entry.agg_id: entry for entry in build_registry()}
    for module_id, agg_id in _COVERED_BY_SELECTOR_ALIAS.items():
        entry = registry[agg_id]
        assert entry.selector([module_id]), f"{module_id} should select {agg_id}"
