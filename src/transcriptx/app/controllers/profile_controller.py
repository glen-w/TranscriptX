"""
Profile controller. List and load analysis profiles. No prompts, no prints.
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.config import (
    get_profile_target_adapter,
    iter_all_profile_target_adapters,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.profile_manager import get_profile_manager


def _get_active_profile_name(target_id: str) -> str:
    """Get active profile name from config."""
    adapter = get_profile_target_adapter(target_id)
    if adapter is None:
        return "default"
    return adapter.get_active_profile_name(get_config())


class ProfileController:
    _ALLOWED_ACTIVATION_SCOPES = {"Project": "project", "Run override": "run"}

    """Orchestrates profile operations. No prompts, no prints."""

    @staticmethod
    def _supports_target(target_id: str) -> bool:
        return get_profile_target_adapter(target_id) is not None

    @staticmethod
    def _is_virtual_default(profile_name: str) -> bool:
        return profile_name == "default"

    def list_supported_targets(self) -> list[str]:
        """List canonical profile target ids supported by runtime/GUI contracts."""
        return [adapter.target_id for adapter in iter_all_profile_target_adapters()]

    def list_profiles(self, target_id: str) -> list[str]:
        """List profile names for a supported target."""
        if not self._supports_target(target_id):
            return []
        pm = get_profile_manager()
        saved = [name for name in pm.list_profiles(target_id) if name != "default"]
        return ["default"] + saved

    def get_active_profile(self, target_id: str) -> str:
        """Get active profile name for a supported target."""
        return _get_active_profile_name(target_id)

    def can_edit_activation_for_scope(self, target_id: str, scope_label: str) -> bool:
        """Return whether activation for target can be edited in given UI scope."""
        scope_key = self._ALLOWED_ACTIVATION_SCOPES.get(scope_label)
        if scope_key is None:
            return False
        adapter = get_profile_target_adapter(target_id)
        if adapter is None:
            return False
        return adapter.supports_scope(scope_key)

    def load_profile(self, target_id: str, name: str) -> dict:
        """Load profile config as dict."""
        if not self._supports_target(target_id):
            return {}
        if self._is_virtual_default(name):
            return {}
        pm = get_profile_manager()
        result = pm.load_profile(target_id, name)
        return result if result is not None else {}

    def save_profile(
        self,
        target_id: str,
        profile_name: str,
        config_dict: dict,
        description: str | None = None,
    ) -> bool:
        if not self._supports_target(target_id):
            return False
        if self._is_virtual_default(profile_name):
            return False
        pm = get_profile_manager()
        return pm.save_profile(target_id, profile_name, config_dict, description)

    def create_profile(
        self,
        target_id: str,
        profile_name: str,
        config_dict: dict,
        description: str | None = None,
    ) -> bool:
        if not self._supports_target(target_id):
            return False
        if self._is_virtual_default(profile_name):
            return False
        pm = get_profile_manager()
        return pm.create_profile(target_id, profile_name, config_dict, description)

    def rename_profile(self, target_id: str, old_name: str, new_name: str) -> bool:
        if not self._supports_target(target_id):
            return False
        if self._is_virtual_default(old_name) or self._is_virtual_default(new_name):
            return False
        pm = get_profile_manager()
        return pm.rename_profile(target_id, old_name, new_name)

    def delete_profile(self, target_id: str, profile_name: str) -> bool:
        if not self._supports_target(target_id):
            return False
        if self._is_virtual_default(profile_name):
            return False
        pm = get_profile_manager()
        return pm.delete_profile(target_id, profile_name)

    def import_profile(
        self,
        target_id: str,
        profile_name: str,
        import_path: str | Path,
        overwrite: bool = False,
    ) -> bool:
        if not self._supports_target(target_id):
            return False
        if self._is_virtual_default(profile_name):
            return False
        pm = get_profile_manager()
        return pm.import_profile(target_id, profile_name, Path(import_path), overwrite)

    def export_profile(
        self, target_id: str, profile_name: str, export_path: str | Path
    ) -> bool:
        if not self._supports_target(target_id):
            return False
        if self._is_virtual_default(profile_name):
            return False
        pm = get_profile_manager()
        return pm.export_profile(target_id, profile_name, Path(export_path))
