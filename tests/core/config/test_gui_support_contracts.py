from __future__ import annotations

from transcriptx.core.config import (
    get_default_config_dict,
    iter_runtime_profile_target_adapters,
    list_supported_profile_target_ids,
    list_runtime_profile_targets,
)
from transcriptx.core.config.gui_support import (
    PROFILE_TARGET_CONTRACTS,
    PROFILE_TARGET_ORDER,
    PROFILE_TARGET_SUPPORT,
)


def test_runtime_profile_targets_match_support_map() -> None:
    runtime_ids = {target.target_id for target in list_runtime_profile_targets()}
    support_ids = {
        target_id
        for target_id, support in PROFILE_TARGET_SUPPORT.items()
        if support.runtime_loaded
    }
    assert runtime_ids == support_ids


def test_activation_keys_exist_in_default_config() -> None:
    defaults = get_default_config_dict()
    for support in list_runtime_profile_targets():
        if support.activation_key == "active_workflow_profile":
            assert "active_workflow_profile" in defaults
        else:
            _, attr = support.activation_key.split(".", 1)
            assert attr in defaults["analysis"]


def test_profile_target_order_workflow_first() -> None:
    target_ids = list_supported_profile_target_ids()
    assert target_ids[0] == "workflow"


def test_supported_target_ids_use_canonical_then_deterministic_non_alpha_tail() -> None:
    target_ids = list_supported_profile_target_ids()
    ordered_prefix = [
        target_id
        for target_id in PROFILE_TARGET_ORDER
        if target_id in PROFILE_TARGET_CONTRACTS
    ]
    deterministic_tail = [
        target_id
        for target_id in PROFILE_TARGET_CONTRACTS.keys()
        if target_id not in PROFILE_TARGET_ORDER
    ]
    assert target_ids == tuple(ordered_prefix + deterministic_tail)


def test_runtime_profile_adapters_resolve_activation_and_config_paths() -> None:
    from transcriptx.core.utils.config.main import TranscriptXConfig

    cfg = TranscriptXConfig()
    for adapter in iter_runtime_profile_target_adapters():
        active = adapter.get_active_profile_name(cfg)
        assert isinstance(active, str)
        assert adapter.get_target_config_obj(cfg) is not None
