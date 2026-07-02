"""Snapshot contract for build_module_definitions registry metadata."""

from __future__ import annotations

from transcriptx.core.domain.module_requirements import Requirement
from transcriptx.core.pipeline.module_registry_specs import build_module_definitions

from .module_registry_snapshot_utils import (
    load_snapshot_fixture,
    normalize_module_definitions,
    observed_spec_keys,
)


def test_build_module_definitions_matches_snapshot() -> None:
    raw = build_module_definitions([Requirement.SEGMENTS])
    normalized = normalize_module_definitions(raw)
    assert normalized == load_snapshot_fixture()


def test_normalizer_covers_all_observed_spec_keys() -> None:
    raw = build_module_definitions([Requirement.SEGMENTS])
    normalized = normalize_module_definitions(raw)

    for module_id, spec in raw.items():
        raw_keys = set(spec.keys())
        normalized_keys = set(normalized["modules"][module_id].keys())
        assert (
            raw_keys <= normalized_keys
        ), f"{module_id}: normalizer dropped keys {raw_keys - normalized_keys}"
        assert (
            normalized_keys <= raw_keys
        ), f"{module_id}: normalizer added keys {normalized_keys - raw_keys}"

    assert observed_spec_keys(raw) == {
        key for module in normalized["modules"].values() for key in module.keys()
    }
