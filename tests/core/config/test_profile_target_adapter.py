"""Tests for profile target adapter."""

from __future__ import annotations

from types import SimpleNamespace

from transcriptx.core.config import (
    get_profile_target_adapter,
    iter_all_profile_target_adapters,
    iter_runtime_profile_target_adapters,
    list_supported_profile_target_ids,
    strip_activation_keys_from_flat_map,
    strip_activation_keys_from_nested_map,
)
from transcriptx.core.config.gui_support import PROFILE_TARGET_CONTRACTS


def test_module_adapter_get_set_active_profile_name() -> None:
    adapter = get_profile_target_adapter("acts")
    assert adapter is not None
    cfg = SimpleNamespace(analysis=SimpleNamespace(active_acts_profile="default"))
    assert adapter.get_active_profile_name(cfg) == "default"
    adapter.set_active_profile_name(cfg, "team")
    assert cfg.analysis.active_acts_profile == "team"


def test_workflow_adapter_get_set_active_profile_name() -> None:
    adapter = get_profile_target_adapter("workflow")
    assert adapter is not None
    cfg = SimpleNamespace(active_workflow_profile="default")
    assert adapter.get_active_profile_name(cfg) == "default"
    adapter.set_active_profile_name(cfg, "nightly")
    assert cfg.active_workflow_profile == "nightly"


def test_adapter_returns_target_config_object() -> None:
    module_adapter = get_profile_target_adapter("qa_analysis")
    workflow_adapter = get_profile_target_adapter("workflow")
    assert module_adapter is not None
    assert workflow_adapter is not None
    cfg = SimpleNamespace(
        analysis=SimpleNamespace(qa_analysis=SimpleNamespace(key="module")),
        workflow=SimpleNamespace(key="workflow"),
    )
    assert module_adapter.get_target_config_obj(cfg).key == "module"
    assert workflow_adapter.get_target_config_obj(cfg).key == "workflow"


def test_iter_all_adapters_matches_supported_order() -> None:
    supported = list_supported_profile_target_ids()
    all_adapters = iter_all_profile_target_adapters()
    assert [a.target_id for a in all_adapters] == list(supported)


def test_runtime_adapters_are_subset_of_all_adapters() -> None:
    runtime_ids = {a.target_id for a in iter_runtime_profile_target_adapters()}
    all_ids = {a.target_id for a in iter_all_profile_target_adapters()}
    assert runtime_ids.issubset(all_ids)


def test_all_contract_targets_resolve_adapters_with_matching_metadata() -> None:
    for target_id, contract in PROFILE_TARGET_CONTRACTS.items():
        adapter = get_profile_target_adapter(target_id)
        assert adapter is not None
        assert adapter.target_id == contract.support.target_id
        assert adapter.activation_key == contract.support.activation_key
        assert adapter.activation_path == contract.support.activation_path
        assert adapter.config_path == contract.support.config_path
        assert adapter.profile_type == contract.support.profile_type
        assert adapter.type_badge == contract.presentation.type_badge


def test_activation_write_uses_single_canonical_api_for_flat_and_serialized_maps() -> (
    None
):
    adapter = get_profile_target_adapter("acts")
    assert adapter is not None
    flat: dict[str, str] = {}
    analysis_map: dict[str, str] = {}
    root_map: dict[str, str] = {}
    adapter.write_activation_value(
        value="team",
        flat_map=flat,
        analysis_map=analysis_map,
        root_map=root_map,
    )
    assert flat[adapter.activation_key] == "team"
    assert analysis_map["active_acts_profile"] == "team"
    assert root_map == {}


def test_activation_strip_helpers_remove_activation_from_flat_and_nested_payloads() -> (
    None
):
    flat = {
        "analysis.active_acts_profile": "team",
        "active_workflow_profile": "nightly",
        "analysis.semantic_model_name": "x",
    }
    nested = {
        "analysis": {
            "active_acts_profile": "team",
            "semantic_model_name": "x",
        },
        "active_workflow_profile": "nightly",
    }
    stripped_flat = strip_activation_keys_from_flat_map(flat)
    stripped_nested = strip_activation_keys_from_nested_map(nested)
    assert "analysis.active_acts_profile" not in stripped_flat
    assert "active_workflow_profile" not in stripped_flat
    assert "active_acts_profile" not in stripped_nested["analysis"]
    assert "active_workflow_profile" not in stripped_nested


def test_activation_strip_helpers_do_not_mutate_inputs() -> None:
    flat = {
        "analysis.active_acts_profile": "team",
        "analysis.semantic_model_name": "x",
    }
    nested = {
        "analysis": {
            "active_acts_profile": "team",
            "semantic_model_name": "x",
        },
        "active_workflow_profile": "nightly",
    }
    flat_before = dict(flat)
    nested_before = {
        "analysis": dict(nested["analysis"]),
        "active_workflow_profile": nested["active_workflow_profile"],
    }
    _ = strip_activation_keys_from_flat_map(flat)
    _ = strip_activation_keys_from_nested_map(nested)
    assert flat == flat_before
    assert nested == nested_before
