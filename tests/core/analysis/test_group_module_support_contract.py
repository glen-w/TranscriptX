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
    "semantic_similarity": "semantic_similarity",
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
        # Finalize-phase modules publish via run finalization, not aggregation.
        if getattr(info, "finalize_phase", False):
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
def test_all_registered_modules_support_group() -> None:
    # tag_extraction is library organisation metadata, not a group cohort module.
    allowed_unsupported = {"tag_extraction"}
    unsupported = [
        module_id
        for module_id in get_available_modules()
        if (info := get_module_info(module_id)) is not None and not info.supports_group
    ]
    unexpected = sorted(set(unsupported) - allowed_unsupported)
    assert not unexpected, f"unexpected supports_group=false: {unexpected}"


@pytest.mark.unit
def test_exclude_from_default_still_omitted_from_group_defaults() -> None:
    defaults = get_default_modules(for_group=True)
    assert "voice_contours" not in defaults


@pytest.mark.unit
def test_alias_modules_map_to_expected_agg_ids() -> None:
    registry = {entry.agg_id: entry for entry in build_registry()}
    for module_id, agg_id in _COVERED_BY_SELECTOR_ALIAS.items():
        entry = registry[agg_id]
        assert entry.selector([module_id]), f"{module_id} should select {agg_id}"


@pytest.mark.unit
def test_insights_family_selectors_fire_for_group_selected_modules() -> None:
    """Individual Insights/LLM modules must select their group aggregation entries."""
    registry = {entry.agg_id: entry for entry in build_registry()}
    expected = {
        "highlights": "highlights",
        "insights": "insights",
        "summary": "summary",
        "llm_summary": "llm_summary",
        "llm_action_items": "llm_action_items",
        "llm_speaker_summary": "llm_speaker_summary",
        "narrative_summary": "narrative_summary",
    }
    for module_id, agg_id in expected.items():
        entry = registry[agg_id]
        assert entry.selector([module_id]), f"{module_id} should select agg {agg_id}"
        # Full selected list still selects when other modules are present.
        assert entry.selector(["stats", module_id, "sentiment"])
