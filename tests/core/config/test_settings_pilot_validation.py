"""Broad validation coverage for Pydantic-owned settings pilots."""

from __future__ import annotations

from typing import Any

import pytest

from transcriptx.core.config import get_default_config_dict, validate_config
from transcriptx.core.config.pydantic_bridge import (
    PYDANTIC_REGISTRY_PILOTS,
    all_pydantic_field_dotpaths,
    is_pydantic_validated_field_key,
)
from transcriptx.core.config.registry import build_registry, flatten

_INVALID_PILOT_CASES: list[dict[str, Any]] = [
    {
        "id": "output_dynamic_charts",
        "payload": {"output": {"dynamic_charts": "maybe"}},
        "dotpath": "output.dynamic_charts",
    },
    {
        "id": "output_dedup_threshold",
        "payload": {"output": {"audio_deduplication_threshold": 1.5}},
        "dotpath": "output.audio_deduplication_threshold",
    },
    {
        "id": "input_file_selection_mode",
        "payload": {"input": {"file_selection_mode": "browse"}},
        "dotpath": "input.file_selection_mode",
    },
    {
        "id": "llm_provider",
        "payload": {"llm": {"provider": "openai"}},
        "dotpath": "llm.provider",
    },
    {
        "id": "llm_request_timeout",
        "payload": {"llm": {"request_timeout": 0}},
        "dotpath": "llm.request_timeout",
    },
    {
        "id": "workflow_timeout",
        "payload": {"workflow": {"timeout_quick_seconds": 0}},
        "dotpath": "workflow.timeout_quick_seconds",
    },
    {
        "id": "workflow_speaker_gate_mode",
        "payload": {"workflow": {"speaker_gate": {"mode": "strict"}}},
        "dotpath": "workflow.speaker_gate.mode",
    },
    {
        "id": "metadata_duration_calculation",
        "payload": {"metadata": {"duration_calculation": "sum"}},
        "dotpath": "metadata.duration_calculation",
    },
    {
        "id": "dashboard_duration_style",
        "payload": {"dashboard": {"duration_summary_style": "verbose"}},
        "dotpath": "dashboard.duration_summary_style",
    },
    {
        "id": "dashboard_overview_behavior",
        "payload": {"dashboard": {"overview_missing_behavior": "hide"}},
        "dotpath": "dashboard.overview_missing_behavior",
    },
    {
        "id": "acts_method",
        "payload": {"analysis": {"acts": {"method": "transformer"}}},
        "dotpath": "analysis.acts.method",
    },
    {
        "id": "semantic_v2_mode",
        "payload": {"analysis": {"semantic_similarity": {"mode": "legacy"}}},
        "dotpath": "analysis.semantic_similarity.mode",
    },
    {
        "id": "audio_target_lufs",
        "payload": {"audio_preprocessing": {"target_lufs": -10.0}},
        "dotpath": "audio_preprocessing.target_lufs",
    },
    {
        "id": "group_analysis_enabled",
        "payload": {"group_analysis": {"enabled": []}},
        "dotpath": "group_analysis.enabled",
    },
]


def test_default_config_has_no_pydantic_validation_errors() -> None:
    errors = validate_config(get_default_config_dict())
    pilot_keys = all_pydantic_field_dotpaths()
    leaked = {key: msgs for key, msgs in errors.items() if key in pilot_keys}
    assert not leaked, leaked


def test_registry_defaults_match_flattened_config_for_pilot_keys() -> None:
    reg = build_registry()
    flat = flatten(get_default_config_dict())
    mismatches: list[str] = []
    for key in all_pydantic_field_dotpaths():
        if key not in flat:
            continue
        meta = reg.get(key)
        if meta is None:
            mismatches.append(f"{key}: missing registry metadata")
            continue
        if flat[key] != meta.default:
            mismatches.append(
                f"{key}: config={flat[key]!r} registry_default={meta.default!r}"
            )
    assert not mismatches, "\n".join(mismatches)


@pytest.mark.parametrize("case", _INVALID_PILOT_CASES, ids=lambda c: c["id"])
def test_invalid_pilot_payload_fails_at_dotpath(case: dict[str, Any]) -> None:
    errors = validate_config(case["payload"])
    assert case["dotpath"] in errors


@pytest.mark.parametrize(
    "spec",
    PYDANTIC_REGISTRY_PILOTS,
    ids=lambda s: s.pilot_id,
)
def test_pilot_default_prefix_validates_clean(spec) -> None:
    flat = flatten(get_default_config_dict())
    prefix = f"{spec.dotpath_prefix}."
    pilot_slice = {key: value for key, value in flat.items() if key.startswith(prefix)}
    if not pilot_slice:
        pytest.skip(f"no default keys under {spec.dotpath_prefix}")
    nested = _unflatten_dotpaths(pilot_slice)
    errors = validate_config(nested)
    leaked = [key for key in errors if key.startswith(spec.dotpath_prefix)]
    assert not leaked, f"{spec.pilot_id}: {leaked}"


def test_non_pydantic_baseline_keys_still_validate_via_registry() -> None:
    errors = validate_config(
        {
            "use_emojis": "not-a-bool",
            "core_mode": 123,
        }
    )
    assert "use_emojis" in errors
    assert "core_mode" in errors
    assert not any(is_pydantic_validated_field_key(key) for key in errors)


def _unflatten_dotpaths(flat: dict[str, Any]) -> dict[str, Any]:
    from transcriptx.core.config.registry import unflatten

    return unflatten(flat)
