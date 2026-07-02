"""Bounded registry metadata vs Pydantic model agreement (choices, defaults, type)."""

from __future__ import annotations

import pytest

from transcriptx.core.config.pydantic_bridge import (
    PYDANTIC_REGISTRY_PILOTS,
    find_pilot_for_dotpath_key,
)
from transcriptx.core.config.pydantic_registry import (
    pydantic_model_to_field_metadata,
    serialize_field_metadata,
)
from transcriptx.core.config.registry import build_registry


def _category_for(spec) -> str:
    if spec.category:
        return spec.category
    if "." in spec.dotpath_prefix:
        return spec.dotpath_prefix.split(".", 1)[0]
    return spec.dotpath_prefix


@pytest.mark.parametrize(
    "spec",
    PYDANTIC_REGISTRY_PILOTS,
    ids=lambda s: s.pilot_id,
)
def test_pilot_registry_choices_defaults_type_match_pydantic_model(spec) -> None:
    """Registry metadata for owned keys matches pydantic_model_to_field_metadata."""
    reg = build_registry()
    expected = pydantic_model_to_field_metadata(
        spec.model,
        dotpath_prefix=spec.dotpath_prefix,
        category=_category_for(spec),
    )
    owned = {
        key
        for key in reg
        if find_pilot_for_dotpath_key(key) is not None
        and find_pilot_for_dotpath_key(key).pilot_id == spec.pilot_id
    }
    assert set(expected) == owned, f"{spec.pilot_id}: expected keys mismatch"
    for key in owned:
        actual = serialize_field_metadata(reg[key])
        exp = serialize_field_metadata(expected[key])
        assert actual["type"] == exp["type"], f"{key}: type"
        assert actual["default"] == exp["default"], f"{key}: default"
        assert actual["choices"] == exp["choices"], f"{key}: choices"


@pytest.mark.parametrize(
    "spec",
    PYDANTIC_REGISTRY_PILOTS,
    ids=lambda s: s.pilot_id,
)
def test_pilot_registry_bounds_match_model_when_present(spec) -> None:
    """min/max agreement only where registry metadata already has bounds."""
    reg = build_registry()
    expected = pydantic_model_to_field_metadata(
        spec.model,
        dotpath_prefix=spec.dotpath_prefix,
        category=_category_for(spec),
    )
    owned = {
        key
        for key in reg
        if find_pilot_for_dotpath_key(key) is not None
        and find_pilot_for_dotpath_key(key).pilot_id == spec.pilot_id
    }
    for key in owned:
        actual_meta = reg[key]
        if actual_meta.min is None and actual_meta.max is None:
            continue
        exp_meta = expected[key]
        if actual_meta.min is not None:
            assert actual_meta.min == exp_meta.min, f"{key}: min"
        if actual_meta.max is not None:
            assert actual_meta.max == exp_meta.max, f"{key}: max"
