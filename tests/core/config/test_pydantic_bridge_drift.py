"""Global drift guards for Pydantic config pilots."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

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
from transcriptx.core.config.registry import build_registry, get_default_config_dict
from transcriptx.core.utils.config import TranscriptXConfig
from transcriptx.core.utils.config.env_key_registry import (
    ENV_KEY_REGISTRY,
    INFRA_ENV_ALLOWLIST,
)

from .delegation_test_utils import without_transcriptx_env

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _normalize_for_json(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_normalize_for_json(v) for v in value]
    if isinstance(value, dict):
        return {k: _normalize_for_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_for_json(v) for v in value]
    if isinstance(value, str):
        return _normalize_pathish(value)
    return value


_REPO = "<REPO>"

# Longest-first Docker/workspace absolute markers under a /data root.
_DATA_ABSOLUTE_MARKERS = (
    "/data/transcripts/metadata/speaker_maps",
    "/data/transcripts/readable",
    "/data/transcripts/metadata",
    "/data/transcripts/imports",
    "/data/transcripts/originals",
    "/data/backups/processing_state",
    "/data/backups/wav",
    "/data/backups",
    "/data/cache/audio_playback",
    "/data/cache/voice",
    "/data/speaker_profiles",
    "/data/recordings/imports",
    "/data/recordings",
    "/data/transcripts",
    "/data/outputs/groups",
    "/data/outputs",
    "/data/preprocessing",
    "/data/corrections",
    "/data/state",
    "/data/groups",
)


def _is_output_root_part(part: str, prev: str | None) -> bool:
    if part == ".test_outputs":
        return True
    if part.startswith("tx-out"):
        return True
    return part == "outputs" and prev in {"data", "mnt"}


def _is_data_root_part(part: str) -> bool:
    return part == "data" or "tx-data" in part


def _normalize_pathish(value: str) -> str:
    """Collapse host-/container-/CI-absolute paths to role-based <REPO>/... forms."""
    if not value.startswith("/"):
        return value

    path = value.replace("\\", "/").rstrip("/")
    if path.startswith("/workspace/"):
        path = path[len("/workspace") :]

    for marker in _DATA_ABSOLUTE_MARKERS:
        idx = path.find(marker)
        if idx >= 0:
            return _REPO + path[idx:]

    dot_tx = path.find("/.transcriptx")
    if dot_tx >= 0:
        return _REPO + path[dot_tx:]

    parts = PurePosixPath(path).parts
    for i, part in enumerate(parts):
        if part == "/":
            continue
        prev = parts[i - 1] if i > 0 else None
        if _is_output_root_part(part, prev):
            rest = parts[i + 1 :]
            suffix = ("/" + "/".join(rest)) if rest else ""
            return f"{_REPO}/.test_outputs{suffix}"
        if _is_data_root_part(part):
            rest = parts[i + 1 :]
            suffix = ("/" + "/".join(rest)) if rest else ""
            return f"{_REPO}/data{suffix}"

    return value


def _normalize_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    out = dict(meta)
    default = out.get("default")
    if isinstance(default, list):
        out["default"] = [_normalize_for_json(v) for v in default]
    else:
        out["default"] = _normalize_for_json(default)
    return out


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
    with without_transcriptx_env():
        reg = build_registry()
        for spec in PYDANTIC_REGISTRY_PILOTS:
            fixture = FIXTURES / f"{spec.pilot_id}_registry_golden.json"
            assert fixture.exists(), f"missing golden fixture for {spec.pilot_id}"
            golden = json.loads(fixture.read_text())
            for key, expected in golden.items():
                assert key in reg, key
                actual = _normalize_metadata(serialize_field_metadata(reg[key]))
                expected_n = _normalize_metadata(expected)
                assert actual == expected_n, f"{key}: {actual!r} != {expected_n!r}"


def test_non_pydantic_registry_matches_baseline() -> None:
    baseline = json.loads(
        (FIXTURES / "non_pydantic_registry_baseline.json").read_text()
    )
    with without_transcriptx_env():
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


def _pilot_defaults_subtree(spec) -> dict:
    """Extract default config subtree for a pilot from get_default_config_dict()."""
    from dataclasses import asdict

    from transcriptx.core.utils.config.analysis import AnalysisConfig

    defaults = get_default_config_dict()
    prefix = spec.dotpath_prefix
    if spec.dataclass_type is not None:
        return asdict(spec.dataclass_type())
    if spec.pilot_id in {
        "quality_filtering_profiles",
        "semantic_similarity_profiles",
        "quick_analysis_settings",
        "full_analysis_settings",
    }:
        return getattr(AnalysisConfig(), spec.pilot_id)
    if prefix == "dashboard":
        dash = defaults["dashboard"]
        keys = list(spec.model.model_fields)
        return {k: dash[k] for k in keys}
    if prefix == "analysis" and spec.pilot_id.startswith("analysis_"):
        inst = AnalysisConfig()
        return {f: getattr(inst, f) for f in spec.model.model_fields}
    parts = prefix.split(".")
    node = defaults
    for part in parts:
        node = node[part]
    return node


def test_pydantic_pilot_defaults_goldens_are_complete() -> None:
    for spec in PYDANTIC_REGISTRY_PILOTS:
        fixture = FIXTURES / f"{spec.pilot_id}_defaults_golden.json"
        assert fixture.exists(), f"missing defaults golden for {spec.pilot_id}"


def test_pydantic_pilot_defaults_match_golden_fixtures() -> None:
    with without_transcriptx_env():
        for spec in PYDANTIC_REGISTRY_PILOTS:
            fixture = FIXTURES / f"{spec.pilot_id}_defaults_golden.json"
            golden = _normalize_for_json(json.loads(fixture.read_text()))
            actual = _normalize_for_json(_pilot_defaults_subtree(spec))
            assert actual == golden, f"{spec.pilot_id}: defaults drift"
