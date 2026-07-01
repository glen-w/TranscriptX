"""Integration tests for profile-backed Pydantic config modules."""

from __future__ import annotations

from typing import Any

import pytest

from transcriptx.core.config import (
    resolve_effective_config,
    save_project_config,
    validate_config,
)
from transcriptx.core.config import persistence as config_persistence
from transcriptx.core.utils.config import TranscriptXConfig

_PROFILE_CASES: list[dict[str, Any]] = [
    {
        "pilot_id": "topic_modeling",
        "config_path": ("analysis", "topic_modeling"),
        "active_key": "active_topic_modeling_profile",
        "active_profile": "team",
        "override_field": "max_features",
        "override_value": 2000,
        "profile_payload": {"max_features": 1500, "min_df": 3},
        "invalid_payload": {"max_features": "not-an-int"},
        "invalid_dotpath": "analysis.topic_modeling.max_features",
    },
    {
        "pilot_id": "qa_analysis",
        "config_path": ("analysis", "qa_analysis"),
        "active_key": "active_qa_analysis_profile",
        "active_profile": "team",
        "override_field": "response_time_threshold",
        "override_value": 15.0,
        "profile_payload": {"response_time_threshold": 12.0, "min_answer_length": 4},
        "invalid_payload": {"min_answer_length": "bad"},
        "invalid_dotpath": "analysis.qa_analysis.min_answer_length",
    },
    {
        "pilot_id": "temporal_dynamics",
        "config_path": ("analysis", "temporal_dynamics"),
        "active_key": "active_temporal_dynamics_profile",
        "active_profile": "team",
        "override_field": "window_size",
        "override_value": 45.0,
        "profile_payload": {"window_size": 60.0, "weight_segment_factor": 0.5},
        "invalid_payload": {"window_size": "slow"},
        "invalid_dotpath": "analysis.temporal_dynamics.window_size",
    },
    {
        "pilot_id": "vectorization",
        "config_path": ("analysis", "vectorization"),
        "active_key": "active_vectorization_profile",
        "active_profile": "team",
        "override_field": "max_features",
        "override_value": 800,
        "profile_payload": {"max_features": 500, "wordcloud_max_features": 200},
        "invalid_payload": {"max_features": "many"},
        "invalid_dotpath": "analysis.vectorization.max_features",
    },
    {
        "pilot_id": "tag_extraction",
        "config_path": ("analysis", "tag_extraction"),
        "active_key": "active_tag_extraction_profile",
        "active_profile": "team",
        "override_field": "early_window_seconds",
        "override_value": 90,
        "profile_payload": {"early_window_seconds": 120, "min_confidence": 0.7},
        "invalid_payload": {"early_segments": "ten"},
        "invalid_dotpath": "analysis.tag_extraction.early_segments",
    },
    {
        "pilot_id": "workflow",
        "config_path": ("workflow",),
        "active_key": "active_workflow_profile",
        "active_profile": "team",
        "override_field": "timeout_quick_seconds",
        "override_value": 7200,
        "profile_payload": {
            "timeout_quick_seconds": 5400,
            "speaker_gate": {"mode": "enforce", "exemplar_count": 3},
        },
        "invalid_payload": {"speaker_gate": {"mode": "invalid-mode"}},
        "invalid_dotpath": "workflow.speaker_gate.mode",
        "nested_assertions": {
            "speaker_gate.mode": "enforce",
            "speaker_gate.exemplar_count": 3,
        },
    },
]


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    cfg_dir = tmp_path / ".transcriptx"
    monkeypatch.setattr(config_persistence, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config_persistence, "CONFIG_DRAFTS_DIR", cfg_dir / "drafts")
    return cfg_dir


def _get_config_attr(cfg: TranscriptXConfig, path: tuple[str, ...]) -> Any:
    current: Any = cfg
    for segment in path:
        current = getattr(current, segment)
    return current


def _nested_get(obj: Any, dotted: str) -> Any:
    current = obj
    for segment in dotted.split("."):
        current = getattr(current, segment)
    return current


@pytest.mark.parametrize("case", _PROFILE_CASES, ids=lambda c: c["pilot_id"])
def test_profile_module_invalid_field_fails_validation(case: dict[str, Any]) -> None:
    root = case["config_path"][0]
    leaf = case["config_path"][-1] if len(case["config_path"]) > 1 else None
    if leaf:
        payload = {root: {leaf: case["invalid_payload"]}}
    else:
        payload = {root: case["invalid_payload"]}
    errors = validate_config(payload)
    assert case["invalid_dotpath"] in errors


@pytest.mark.parametrize("case", _PROFILE_CASES, ids=lambda c: c["pilot_id"])
def test_profile_module_project_override_resolves(
    case: dict[str, Any], config_dir, monkeypatch
) -> None:
    root = case["config_path"][0]
    leaf = case["config_path"][-1] if len(case["config_path"]) > 1 else None
    field = case["override_field"]
    value = case["override_value"]
    if leaf:
        save_project_config({root: {leaf: {field: value}}})
    else:
        save_project_config({root: {field: value}})
    resolved = resolve_effective_config(run_dir=None)
    target = _get_config_attr(resolved.effective_config, case["config_path"])
    assert getattr(target, field) == value
    dotpath = ".".join(case["config_path"] + (field,))
    assert resolved.sources_by_key.get(dotpath) == "project"


@pytest.mark.parametrize("case", _PROFILE_CASES, ids=lambda c: c["pilot_id"])
def test_profile_module_payload_roundtrip(
    case: dict[str, Any], config_dir, monkeypatch
) -> None:
    root = case["config_path"][0]
    leaf = case["config_path"][-1] if len(case["config_path"]) > 1 else None
    active_key = case["active_key"]
    if leaf:
        save_project_config(
            {
                root: {
                    active_key: case["active_profile"],
                    leaf: case["profile_payload"],
                }
            }
        )
    else:
        save_project_config(
            {
                active_key: case["active_profile"],
                root: case["profile_payload"],
            }
        )
    resolved = resolve_effective_config(run_dir=None)
    target = _get_config_attr(resolved.effective_config, case["config_path"])
    for key, expected in case["profile_payload"].items():
        if isinstance(expected, dict):
            nested = getattr(target, key)
            for sub_key, sub_val in expected.items():
                assert getattr(nested, sub_key) == sub_val
        else:
            assert getattr(target, key) == expected
    if leaf:
        assert (
            getattr(_get_config_attr(resolved.effective_config, (root,)), active_key)
            == case["active_profile"]
        )
    else:
        assert getattr(resolved.effective_config, active_key) == case["active_profile"]
    for dotted, expected in case.get("nested_assertions", {}).items():
        assert _nested_get(target, dotted) == expected
