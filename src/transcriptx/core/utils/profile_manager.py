"""Profile Manager for TranscriptX profile artifacts."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.path_safety import (
    assert_path_under_root,
    assert_safe_path_segment,
)
from transcriptx.core.utils.paths import PROFILES_DIR

logger = get_logger()


class ProfileManager:
    """Manages module/workflow configuration profiles."""

    def __init__(self, profiles_dir: Path | None = None):
        self.profiles_dir = profiles_dir or PROFILES_DIR
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def is_virtual_default_profile_name(profile_name: str) -> bool:
        """Return True for the non-persistable virtual ``default`` profile."""
        return profile_name == "default"

    @staticmethod
    def _is_virtual_default(profile_name: str) -> bool:
        return ProfileManager.is_virtual_default_profile_name(profile_name)

    @staticmethod
    def _normalize_profile_payload(
        module_name: str,
        profile_name: str,
        payload: dict[str, Any],
        *,
        strict_identity: bool = True,
    ) -> dict[str, Any] | None:
        """Validate profile payload shape and identity invariants."""
        if not isinstance(payload, dict):
            return None
        config_obj = payload.get("config")
        if not isinstance(config_obj, dict):
            return None
        raw_module = payload.get("module")
        if raw_module is not None and raw_module != module_name:
            return None
        raw_name = payload.get("name")
        if strict_identity and raw_name is not None and raw_name != profile_name:
            return None
        description = payload.get("description")
        if description is not None and not isinstance(description, str):
            return None
        return {
            "name": profile_name,
            "module": module_name,
            "description": description or f"Profile for {module_name}",
            "config": config_obj,
        }

    def _validated_import_payload(
        self, module_name: str, profile_name: str, import_path: Path
    ) -> dict[str, Any] | None:
        try:
            with open(import_path, "r") as f:
                payload = json.load(f)
        except json.JSONDecodeError:
            return None
        return self._normalize_profile_payload(module_name, profile_name, payload)

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict[str, Any]) -> bool:
        tmp_path: str | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(
                prefix=".profile_tmp_",
                suffix=".json",
                dir=str(path.parent),
            )
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, path)
            return True
        except Exception:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            return False

    def get_profile_path(self, module_name: str, profile_name: str) -> Path:
        module_seg = assert_safe_path_segment(module_name, what="profile module")
        name_seg = assert_safe_path_segment(profile_name, what="profile name")
        module_dir = self.profiles_dir / module_seg
        module_dir.mkdir(parents=True, exist_ok=True)
        dest = module_dir / f"{name_seg}.json"
        assert_path_under_root(
            dest, self.profiles_dir, what="profile path", reject_symlink_root=False
        )
        return dest

    def _profile_path_or_none(
        self, module_name: str, profile_name: str
    ) -> Path | None:
        try:
            return self.get_profile_path(module_name, profile_name)
        except ValueError:
            logger.warning(
                "Rejected unsafe profile path %s/%s", module_name, profile_name
            )
            return None

    def load_profile(
        self, module_name: str, profile_name: str
    ) -> dict[str, Any] | None:
        if self._is_virtual_default(profile_name):
            return None
        profile_path = self._profile_path_or_none(module_name, profile_name)
        if profile_path is None:
            return None
        if not profile_path.exists():
            logger.debug(
                f"Profile {profile_name} for {module_name} does not exist at {profile_path}"
            )
            return None
        try:
            with open(profile_path, "r") as f:
                profile_data = json.load(f)
            normalized = self._normalize_profile_payload(
                module_name, profile_name, profile_data
            )
            if normalized is None:
                logger.error(
                    f"Invalid profile payload for {module_name}/{profile_name} at {profile_path}"
                )
                return None
            logger.debug(f"Loaded profile {profile_name} for {module_name}")
            return normalized
        except Exception as exc:
            logger.error(
                f"Failed to load profile {profile_name} for {module_name}: {exc}"
            )
            return None

    def save_profile(
        self,
        module_name: str,
        profile_name: str,
        config_dict: dict[str, Any],
        description: str | None = None,
        *,
        overwrite: bool = True,
    ) -> bool:
        if self._is_virtual_default(profile_name):
            logger.warning("Cannot persist virtual default profile for %s", module_name)
            return False
        profile_path = self._profile_path_or_none(module_name, profile_name)
        if profile_path is None:
            return False
        if profile_path.exists() and not overwrite:
            logger.warning(
                f"Profile {profile_name} for {module_name} already exists. Use overwrite=True to replace."
            )
            return False
        try:
            profile_data = self._normalize_profile_payload(
                module_name,
                profile_name,
                {
                    "name": profile_name,
                    "module": module_name,
                    "description": description or f"Profile for {module_name}",
                    "config": config_dict,
                },
            )
            if profile_data is None:
                logger.error(
                    f"Invalid profile payload for {module_name}/{profile_name}: malformed data"
                )
                return False
            if not self._atomic_write_json(profile_path, profile_data):
                return False
            logger.info(
                f"Saved profile {profile_name} for {module_name} to {profile_path}"
            )
            return True
        except Exception as exc:
            logger.error(
                f"Failed to save profile {profile_name} for {module_name}: {exc}"
            )
            return False

    def create_profile(
        self,
        module_name: str,
        profile_name: str,
        config_dict: dict[str, Any],
        description: str | None = None,
    ) -> bool:
        """Create a new profile and fail if destination already exists."""
        return self.save_profile(
            module_name,
            profile_name,
            config_dict,
            description,
            overwrite=False,
        )

    def list_profiles(self, module_name: str) -> list[str]:
        try:
            module_seg = assert_safe_path_segment(module_name, what="profile module")
        except ValueError:
            logger.warning("Rejected unsafe profile module for list: %s", module_name)
            return []
        module_dir = self.profiles_dir / module_seg
        if not module_dir.exists():
            return []
        profiles = [p for p in module_dir.glob("*.json") if p.stem != "default"]
        ordered_saved = [
            p.stem
            for p in sorted(
                profiles,
                key=lambda p: (p.stat().st_mtime_ns, p.stem.casefold()),
                reverse=True,
            )
        ]
        return ordered_saved

    def delete_profile(self, module_name: str, profile_name: str) -> bool:
        if self._is_virtual_default(profile_name):
            logger.warning(f"Cannot delete default profile for {module_name}")
            return False
        profile_path = self._profile_path_or_none(module_name, profile_name)
        if profile_path is None:
            return False
        if not profile_path.exists():
            logger.warning(f"Profile {profile_name} for {module_name} does not exist")
            return False
        try:
            profile_path.unlink()
            logger.info(f"Deleted profile {profile_name} for {module_name}")
            return True
        except Exception as exc:
            logger.error(
                f"Failed to delete profile {profile_name} for {module_name}: {exc}"
            )
            return False

    def profile_exists(self, module_name: str, profile_name: str) -> bool:
        if self._is_virtual_default(profile_name):
            return False
        profile_path = self._profile_path_or_none(module_name, profile_name)
        if profile_path is None:
            return False
        return profile_path.exists()

    def export_profile(
        self, module_name: str, profile_name: str, export_path: Path
    ) -> bool:
        if self._is_virtual_default(profile_name):
            logger.warning(f"Cannot export default profile for {module_name}")
            return False
        profile_path = self._profile_path_or_none(module_name, profile_name)
        if profile_path is None:
            return False
        if not profile_path.exists():
            logger.warning(f"Profile {profile_name} for {module_name} does not exist")
            return False
        try:
            shutil.copy2(profile_path, export_path)
            logger.info(
                f"Exported profile {profile_name} for {module_name} to {export_path}"
            )
            return True
        except Exception as exc:
            logger.error(
                f"Failed to export profile {profile_name} for {module_name}: {exc}"
            )
            return False

    def import_profile(
        self,
        module_name: str,
        profile_name: str,
        import_path: Path,
        overwrite: bool = False,
    ) -> bool:
        if self._is_virtual_default(profile_name):
            logger.warning(f"Cannot import into default profile for {module_name}")
            return False
        if not import_path.exists():
            logger.error(f"Import path {import_path} does not exist")
            return False
        profile_path = self._profile_path_or_none(module_name, profile_name)
        if profile_path is None:
            return False
        if profile_path.exists() and not overwrite:
            logger.warning(
                f"Profile {profile_name} for {module_name} already exists. Use overwrite=True to replace."
            )
            return False
        try:
            validated_payload = self._validated_import_payload(
                module_name, profile_name, import_path
            )
            if validated_payload is None:
                logger.error(
                    f"Invalid profile payload for import {import_path} into {module_name}/{profile_name}"
                )
                return False
            if not self._atomic_write_json(profile_path, validated_payload):
                logger.error(
                    f"Failed atomic write for imported profile {module_name}/{profile_name}"
                )
                return False
            logger.info(
                f"Imported profile {profile_name} for {module_name} from {import_path}"
            )
            return True
        except Exception as exc:
            logger.error(
                f"Failed to import profile {profile_name} for {module_name}: {exc}"
            )
            return False

    def rename_profile(self, module_name: str, old_name: str, new_name: str) -> bool:
        if self._is_virtual_default(old_name) or self._is_virtual_default(new_name):
            logger.warning(f"Cannot rename default profile for {module_name}")
            return False
        old_path = self._profile_path_or_none(module_name, old_name)
        new_path = self._profile_path_or_none(module_name, new_name)
        if old_path is None or new_path is None:
            return False
        if not old_path.exists():
            logger.warning(f"Profile {old_name} for {module_name} does not exist")
            return False
        if new_path.exists():
            logger.warning(f"Profile {new_name} for {module_name} already exists")
            return False
        try:
            with open(old_path, "r") as f:
                old_payload = json.load(f)
            normalized_new = self._normalize_profile_payload(
                module_name, new_name, old_payload, strict_identity=False
            )
            if normalized_new is None:
                logger.error(
                    f"Cannot normalize payload for rename {module_name}: {old_name} -> {new_name}"
                )
                return False
            if not self._atomic_write_json(new_path, normalized_new):
                logger.error(
                    f"Atomic write failed for renamed payload {module_name}: {old_name} -> {new_name}"
                )
                return False
            old_path.unlink()
            logger.info(f"Renamed profile {old_name} to {new_name} for {module_name}")
            return True
        except Exception as exc:
            if old_path.exists() and new_path.exists():
                try:
                    new_path.unlink()
                except OSError:
                    pass
            logger.error(
                f"Failed to rename profile {old_name} to {new_name} for {module_name}: {exc}"
            )
            return False


_profile_manager: ProfileManager | None = None


def get_profile_manager() -> ProfileManager:
    """Get the global ProfileManager instance."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager
