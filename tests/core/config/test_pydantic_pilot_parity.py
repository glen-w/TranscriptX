"""Structural ownership and defaults parity for all Pydantic config pilots."""

from __future__ import annotations

from dataclasses import asdict

import pytest

from transcriptx.core.config.pydantic_bridge import (
    PYDANTIC_REGISTRY_PILOTS,
    all_pydantic_field_dotpaths,
    find_pilot_for_dotpath_key,
    serialize_non_pydantic_registry_baseline,
)
from transcriptx.core.config.pydantic_registry import collect_model_leaf_dotpaths
from transcriptx.core.config.registry import build_registry
from transcriptx.core.utils.config.analysis import AnalysisConfig

_DICT_PROFILE_PILOTS = frozenset(
    {
        "quality_filtering_profiles",
        "semantic_similarity_v2_profiles",
        "quick_analysis_settings",
        "full_analysis_settings",
    }
)

_ANALYSIS_PARTIAL_PREFIX = "analysis_"


def test_every_registry_key_has_exactly_one_owner() -> None:
    reg = build_registry()
    pilot_keys = all_pydantic_field_dotpaths()
    baseline = serialize_non_pydantic_registry_baseline(reg)
    for key in reg:
        in_pilot = key in pilot_keys
        in_baseline = key in baseline
        assert in_pilot ^ in_baseline, f"{key}: pilot={in_pilot} baseline={in_baseline}"


def test_pilot_leaf_paths_match_collect_model_leaf_dotpaths() -> None:
    reg = build_registry()
    for spec in PYDANTIC_REGISTRY_PILOTS:
        expected = collect_model_leaf_dotpaths(
            spec.model,
            dotpath_prefix=spec.dotpath_prefix,
        )
        owned = {
            key
            for key in reg
            if find_pilot_for_dotpath_key(key) is not None
            and find_pilot_for_dotpath_key(key).pilot_id == spec.pilot_id
        }
        assert owned == set(expected), f"{spec.pilot_id}: {owned ^ set(expected)}"


def test_pilot_leaf_keys_disjoint() -> None:
    owners: dict[str, str] = {}
    for spec in PYDANTIC_REGISTRY_PILOTS:
        for key in collect_model_leaf_dotpaths(
            spec.model,
            dotpath_prefix=spec.dotpath_prefix,
        ):
            assert (
                key not in owners
            ), f"{key} claimed by {owners[key]} and {spec.pilot_id}"
            owners[key] = spec.pilot_id


@pytest.mark.parametrize(
    "spec",
    [s for s in PYDANTIC_REGISTRY_PILOTS if s.dataclass_type is not None],
    ids=lambda s: s.pilot_id,
)
def test_dataclass_pilot_defaults_match(spec) -> None:
    assert spec.model().model_dump() == asdict(spec.dataclass_type())


@pytest.mark.parametrize(
    "spec",
    [
        s
        for s in PYDANTIC_REGISTRY_PILOTS
        if s.pilot_id.startswith(_ANALYSIS_PARTIAL_PREFIX)
    ],
    ids=lambda s: s.pilot_id,
)
def test_partial_analysis_pilot_defaults_match(spec) -> None:
    inst = AnalysisConfig()
    expected = {name: getattr(inst, name) for name in spec.model.model_fields}
    assert spec.model().model_dump() == expected


@pytest.mark.parametrize(
    "pilot_id,payload_attr",
    [
        ("quality_filtering_profiles", "quality_filtering_profiles"),
        ("semantic_similarity_v2_profiles", "semantic_similarity_v2_profiles"),
        ("quick_analysis_settings", "quick_analysis_settings"),
        ("full_analysis_settings", "full_analysis_settings"),
    ],
)
def test_dict_profile_pilot_defaults_match(pilot_id: str, payload_attr: str) -> None:
    spec = next(s for s in PYDANTIC_REGISTRY_PILOTS if s.pilot_id == pilot_id)
    runtime = getattr(AnalysisConfig(), payload_attr)
    assert spec.model().model_dump() == runtime
