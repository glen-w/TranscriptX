"""Global drift guards for Pydantic config pilots."""

from __future__ import annotations

import json
from pathlib import Path

from transcriptx.core.config.pydantic_bridge import (
    PYDANTIC_REGISTRY_PILOTS,
    all_pydantic_field_dotpaths,
    dotpath_belongs_to_model,
    find_pilot_for_dotpath_key,
    serialize_non_pydantic_registry_baseline,
)
from transcriptx.core.config.pydantic_registry import (
    collect_model_leaf_dotpaths,
    serialize_field_metadata,
)
from transcriptx.core.config.registry import build_registry
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.env_key_registry import (
    ENV_KEY_REGISTRY,
    INFRA_ENV_ALLOWLIST,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _walk_config_path(root: object, path: tuple[str, ...]) -> object:
    current = root
    for segment in path:
        current = getattr(current, segment)
    return current


def test_env_registry_target_paths_resolve_on_config() -> None:
    cfg = TranscriptXConfig()
    for entry in ENV_KEY_REGISTRY:
        if entry.env_name in INFRA_ENV_ALLOWLIST:
            continue
        _walk_config_path(cfg, entry.target_path)


def test_env_registry_pydantic_paths_match_model_fields() -> None:
    for entry in ENV_KEY_REGISTRY:
        if entry.env_name in INFRA_ENV_ALLOWLIST:
            continue
        dotpath = ".".join(entry.target_path)
        spec = find_pilot_for_dotpath_key(dotpath)
        if spec is None:
            continue
        assert dotpath_belongs_to_model(
            dotpath,
            dotpath_prefix=spec.dotpath_prefix,
            model=spec.model,
        ), f"{entry.env_name} -> {dotpath} not on {spec.pilot_id} model"


def test_pydantic_pilot_fields_appear_in_registry() -> None:
    reg = build_registry()
    for spec in PYDANTIC_REGISTRY_PILOTS:
        for key in collect_model_leaf_dotpaths(
            spec.model,
            dotpath_prefix=spec.dotpath_prefix,
        ):
            assert key in reg, key


def test_pydantic_pilot_registry_goldens_are_complete() -> None:
    reg = build_registry()
    for spec in PYDANTIC_REGISTRY_PILOTS:
        fixture = FIXTURES / f"{spec.pilot_id}_registry_golden.json"
        assert fixture.exists(), f"missing golden fixture for {spec.pilot_id}"
        golden_keys = set(json.loads(fixture.read_text()).keys())
        owned = {
            key
            for key in reg
            if find_pilot_for_dotpath_key(key) is not None
            and find_pilot_for_dotpath_key(key).pilot_id == spec.pilot_id
        }
        missing_from_golden = owned - golden_keys
        extra_in_golden = golden_keys - owned
        assert owned == golden_keys, (
            f"{spec.pilot_id}: owned-golden={sorted(missing_from_golden)} "
            f"golden-owned={sorted(extra_in_golden)}"
        )


def test_pydantic_pilot_registry_matches_golden_fixtures() -> None:
    reg = build_registry()
    for spec in PYDANTIC_REGISTRY_PILOTS:
        fixture = FIXTURES / f"{spec.pilot_id}_registry_golden.json"
        assert fixture.exists(), f"missing golden fixture for {spec.pilot_id}"
        golden = json.loads(fixture.read_text())
        for key, expected in golden.items():
            assert key in reg, key
            actual = serialize_field_metadata(reg[key])
            assert actual == expected, f"{key}: {actual!r} != {expected!r}"


def test_non_pydantic_registry_matches_baseline() -> None:
    baseline = json.loads(
        (FIXTURES / "non_pydantic_registry_baseline.json").read_text()
    )
    reg = build_registry()
    actual = serialize_non_pydantic_registry_baseline(reg)
    for key, expected in baseline.items():
        assert key in actual, key
        assert actual[key] == expected, f"{key}: {actual[key]!r} != {expected!r}"


def test_pydantic_field_dotpaths_disjoint_from_non_pydantic_baseline() -> None:
    pilot_keys = all_pydantic_field_dotpaths()
    baseline = json.loads(
        (FIXTURES / "non_pydantic_registry_baseline.json").read_text()
    )
    overlap = pilot_keys & set(baseline)
    assert not overlap, f"pilot keys leaked into baseline: {overlap}"
