"""Structural registry ownership audit for Pydantic config pilots."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.config.pydantic_bridge import (
    PYDANTIC_REGISTRY_PILOTS,
    all_pydantic_field_dotpaths,
    find_pilot_for_dotpath_key,
    serialize_non_pydantic_registry_baseline,
)
from transcriptx.core.config.pydantic_registry import collect_model_leaf_dotpaths
from transcriptx.core.config.registry import (
    build_registry,
    flatten,
    get_default_config_dict,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_registry_key_count_matches_pilot_plus_baseline() -> None:
    reg = build_registry()
    pilot_keys = all_pydantic_field_dotpaths()
    baseline_keys = set(serialize_non_pydantic_registry_baseline(reg))
    assert len(reg) == len(pilot_keys) + len(baseline_keys)


def test_every_registry_key_has_exactly_one_owner() -> None:
    reg = build_registry()
    pilot_keys = all_pydantic_field_dotpaths()
    baseline = serialize_non_pydantic_registry_baseline(reg)
    for key in reg:
        in_pilot = key in pilot_keys
        in_baseline = key in baseline
        assert in_pilot ^ in_baseline, f"{key}: pilot={in_pilot} baseline={in_baseline}"


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


def test_find_pilot_matches_collect_leaf_dotpaths() -> None:
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


def test_pydantic_owned_keys_visible_in_default_config_dict() -> None:
    pilot_keys = all_pydantic_field_dotpaths()
    visible = set(flatten(get_default_config_dict()))
    missing = sorted(pilot_keys - visible)
    assert (
        not missing
    ), "Pydantic-owned keys missing from TranscriptXConfig.to_dict(): " + ", ".join(
        missing
    )


def test_pydantic_owned_visible_values_match_registry_defaults() -> None:
    reg = build_registry()
    flat = flatten(get_default_config_dict())
    mismatches: list[str] = []
    for key in sorted(all_pydantic_field_dotpaths()):
        if key not in flat:
            mismatches.append(f"{key}: missing from to_dict()")
            continue
        meta = reg.get(key)
        if meta is None:
            mismatches.append(f"{key}: missing registry metadata")
            continue
        if flat[key] != meta.default:
            mismatches.append(f"{key}: to_dict={flat[key]!r} registry={meta.default!r}")
    assert not mismatches, "\n".join(mismatches)


def test_baseline_matches_committed_fixture() -> None:
    reg = build_registry()
    expected = json.loads(
        (FIXTURES / "non_pydantic_registry_baseline.json").read_text()
    )
    actual = serialize_non_pydantic_registry_baseline(reg)
    assert (
        len(actual) == 10
    ), f"expected 10 baseline keys, got {len(actual)}: {sorted(actual)}"
    assert set(actual) == set(expected)
    unexpected = set(actual) - set(expected)
    assert not unexpected, f"undocumented non-Pydantic keys: {sorted(unexpected)}"


def test_no_orphan_registry_keys() -> None:
    """Every registry key is owned by a Pydantic pilot or the non-Pydantic baseline."""
    reg = build_registry()
    pilot_keys = all_pydantic_field_dotpaths()
    baseline_keys = set(serialize_non_pydantic_registry_baseline(reg))
    orphans = sorted(set(reg) - pilot_keys - baseline_keys)
    assert not orphans, "registry-only keys with no owner: " + ", ".join(orphans)


def _build_ownership_snapshot() -> dict:
    reg = build_registry()
    pilot_keys = all_pydantic_field_dotpaths()
    baseline = serialize_non_pydantic_registry_baseline(reg)
    per_pilot: dict[str, int] = {}
    for spec in PYDANTIC_REGISTRY_PILOTS:
        per_pilot[spec.pilot_id] = len(
            collect_model_leaf_dotpaths(
                spec.model,
                dotpath_prefix=spec.dotpath_prefix,
            )
        )
    baseline_reasons = {
        "active_workflow_profile": "profile activation selector",
        "analysis.active_acts_profile": "profile activation selector",
        "analysis.active_qa_analysis_profile": "profile activation selector",
        "analysis.active_semantic_similarity_v2_profile": "profile activation selector",
        "analysis.active_tag_extraction_profile": "profile activation selector",
        "analysis.active_temporal_dynamics_profile": "profile activation selector",
        "analysis.active_topic_modeling_profile": "profile activation selector",
        "analysis.active_vectorization_profile": "profile activation selector",
        "core_mode": "install/runtime flag — permanent legacy",
        "use_emojis": "global flag — permanent legacy",
    }
    return {
        "total_registry_keys": len(reg),
        "pydantic_owned_keys": len(pilot_keys),
        "non_pydantic_baseline_keys": len(baseline),
        "pilot_count": len(PYDANTIC_REGISTRY_PILOTS),
        "per_pilot_key_counts": per_pilot,
        "baseline_keys": {
            k: {"reason": baseline_reasons.get(k, "intentional non-Pydantic baseline")}
            for k in sorted(baseline)
        },
        "deferred_keys": {},
    }


def test_ownership_snapshot_matches_committed_fixture() -> None:
    expected = json.loads((FIXTURES / "registry_ownership_snapshot.json").read_text())
    actual = _build_ownership_snapshot()
    assert actual == expected


def test_ownership_invariant_counts() -> None:
    """Delegation PRs must preserve pilot / owned / baseline totals."""
    snap = _build_ownership_snapshot()
    assert snap["pilot_count"] == 41
    assert snap["pydantic_owned_keys"] == 598
    assert snap["non_pydantic_baseline_keys"] == 10
    assert snap["total_registry_keys"] == 608
