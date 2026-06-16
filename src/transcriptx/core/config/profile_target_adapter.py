"""Canonical adapters for profile target activation/config access."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .gui_support import (
    PROFILE_TARGET_CONTRACTS,
    ProfileTargetContract,
    ProfileType,
    ScopeName,
    list_runtime_profile_targets,
)


@dataclass(frozen=True)
class ProfileTargetAdapter:
    """Resolved target adapter for one profile-support entry."""

    contract: ProfileTargetContract

    @property
    def target_id(self) -> str:
        return self.contract.support.target_id

    @property
    def activation_key(self) -> str:
        return self.contract.support.activation_key

    @property
    def profile_type(self) -> str:
        return self.contract.support.profile_type

    @property
    def type_badge(self) -> str:
        return self.contract.presentation.type_badge

    @property
    def activation_label(self) -> str:
        return self.contract.presentation.activation_label

    @property
    def target_label(self) -> str:
        return self.contract.presentation.target_label

    @property
    def guided_fields(self) -> tuple[str, ...]:
        return self.contract.edit_support.guided_fields

    @property
    def order_index(self) -> int:
        return self.contract.presentation.order_index

    @property
    def allow_raw_json_fallback(self) -> bool:
        return self.contract.edit_support.allow_raw_json_fallback

    @property
    def activation_path(self) -> tuple[str, ...]:
        return self.contract.support.activation_path

    @property
    def config_path(self) -> tuple[str, ...]:
        return self.contract.support.config_path

    @staticmethod
    def _get_attr_path(obj: Any, path: tuple[str, ...], default: Any = None) -> Any:
        cur = obj
        for segment in path:
            if cur is None:
                return default
            cur = getattr(cur, segment, None)
        return default if cur is None else cur

    @staticmethod
    def _set_attr_path(obj: Any, path: tuple[str, ...], value: Any) -> bool:
        if not path:
            return False
        cur = obj
        for segment in path[:-1]:
            cur = getattr(cur, segment, None)
            if cur is None:
                return False
        setattr(cur, path[-1], value)
        return True

    @staticmethod
    def _get_mapping_path(
        payload: dict[str, Any], path: tuple[str, ...]
    ) -> tuple[bool, Any]:
        cur: Any = payload
        for segment in path:
            if not isinstance(cur, dict) or segment not in cur:
                return (False, None)
            cur = cur[segment]
        return (True, cur)

    def get_active_profile_name(self, config: Any) -> str:
        return str(self._get_attr_path(config, self.activation_path, default="default"))

    def set_active_profile_name(self, config: Any, profile_name: str) -> None:
        self._set_attr_path(config, self.activation_path, profile_name)

    def get_target_config_obj(self, config: Any) -> Any | None:
        return self._get_attr_path(config, self.config_path, default=None)

    def get_activation_from_payload(self, payload: dict[str, Any]) -> tuple[bool, str]:
        found, value = self._get_mapping_path(payload, self.activation_path)
        if not found:
            return (False, "default")
        return (True, str(value))

    def get_target_payload(
        self, payload: dict[str, Any]
    ) -> tuple[bool, dict[str, Any]]:
        found, value = self._get_mapping_path(payload, self.config_path)
        if not found or not isinstance(value, dict):
            return (False, {})
        return (True, value)

    def write_activation_value(
        self,
        *,
        value: str,
        flat_map: dict[str, Any],
        analysis_map: dict[str, Any] | None = None,
        root_map: dict[str, Any] | None = None,
    ) -> None:
        """Canonical activation write API for flat and nested serialized maps."""
        flat_map[self.activation_key] = value
        if analysis_map is None or root_map is None:
            return
        if len(self.activation_path) >= 2 and self.activation_path[0] == "analysis":
            analysis_map[self.activation_path[-1]] = value
            return
        root_map[self.activation_key] = value

    def supports_scope(self, scope: ScopeName) -> bool:
        return scope in self.contract.support.scopes

    def activation_scope_label(self, scope: ScopeName) -> str:
        return self.contract.presentation.scope_labels[scope]

    def matches_type(self, profile_type: ProfileType) -> bool:
        return self.profile_type == profile_type


def get_profile_target_adapter(target_id: str) -> ProfileTargetAdapter | None:
    contract = PROFILE_TARGET_CONTRACTS.get(target_id)
    if contract is None:
        return None
    return ProfileTargetAdapter(contract=contract)


def iter_runtime_profile_target_adapters() -> tuple[ProfileTargetAdapter, ...]:
    return tuple(
        ProfileTargetAdapter(contract=PROFILE_TARGET_CONTRACTS[s.target_id])
        for s in list_runtime_profile_targets()
    )


def iter_all_profile_target_adapters() -> tuple[ProfileTargetAdapter, ...]:
    adapters: list[ProfileTargetAdapter] = []
    from .gui_support import list_supported_profile_target_ids

    for target_id in list_supported_profile_target_ids():
        adapter = get_profile_target_adapter(target_id)
        if adapter is not None:
            adapters.append(adapter)
    return tuple(adapters)


def strip_activation_keys_from_flat_map(flat_map: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``flat_map`` with adapter-owned activation keys removed."""
    stripped = dict(flat_map)
    for adapter in iter_all_profile_target_adapters():
        stripped.pop(adapter.activation_key, None)
    return stripped


def strip_activation_keys_from_nested_map(
    config_map: dict[str, Any],
) -> dict[str, Any]:
    """Return a deep copy of ``config_map`` with adapter-owned activation keys removed."""
    stripped = copy.deepcopy(config_map)
    for adapter in iter_all_profile_target_adapters():
        path = adapter.activation_path
        if len(path) == 1:
            stripped.pop(path[0], None)
            continue
        cur: Any = stripped
        for segment in path[:-1]:
            if not isinstance(cur, dict):
                cur = None
                break
            cur = cur.get(segment)
        if isinstance(cur, dict):
            cur.pop(path[-1], None)
    return stripped
