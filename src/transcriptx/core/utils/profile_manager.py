"""
Profile Manager for TranscriptX.

This module provides functionality for managing module-specific configuration profiles.
Profiles allow users to save and load named sets of configuration choices for each module.
"""

import json
import shutil
from pathlib import Path
from typing import Any

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import PROFILES_DIR

logger = get_logger()


class ProfileManager:
    """Manages module-specific configuration profiles."""

    def __init__(self, profiles_dir: Path | None = None):
        """
        Initialize the ProfileManager.

        Args:
            profiles_dir: Optional custom directory for profiles. Defaults to data/profiles/
        """
        self.profiles_dir = profiles_dir or PROFILES_DIR
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def get_profile_path(self, module_name: str, profile_name: str) -> Path:
        """
        Get the file path for a profile.

        Args:
            module_name: Name of the module (e.g., "topic_modeling")
            profile_name: Name of the profile (e.g., "default")

        Returns:
            Path to the profile JSON file
        """
        module_dir = self.profiles_dir / module_name
        module_dir.mkdir(parents=True, exist_ok=True)
        return module_dir / f"{profile_name}.json"

    def load_profile(
        self, module_name: str, profile_name: str
    ) -> dict[str, Any] | None:
        """
        Load a profile from disk.

        Args:
            module_name: Name of the module
            profile_name: Name of the profile

        Returns:
            Dictionary with profile settings, or None if profile doesn't exist
        """
        profile_path = self.get_profile_path(module_name, profile_name)

        if not profile_path.exists():
            logger.debug(
                f"Profile {profile_name} for {module_name} does not exist at {profile_path}"
            )
            return None

        try:
            with open(profile_path, "r") as f:
                profile_data = json.load(f)
            logger.debug(f"Loaded profile {profile_name} for {module_name}")
            return profile_data
        except Exception as e:
            logger.error(
                f"Failed to load profile {profile_name} for {module_name}: {e}"
            )
            return None

    def save_profile(
        self,
        module_name: str,
        profile_name: str,
        config_dict: dict[str, Any],
        description: str | None = None,
    ) -> bool:
        """
        Save a profile to disk.

        Args:
            module_name: Name of the module
            profile_name: Name of the profile
            config_dict: Configuration dictionary to save
            description: Optional description of the profile

        Returns:
            True if successful, False otherwise
        """
        profile_path = self.get_profile_path(module_name, profile_name)

        try:
            profile_data = {
                "name": profile_name,
                "module": module_name,
                "description": description or f"Profile for {module_name}",
                "config": config_dict,
            }

            with open(profile_path, "w") as f:
                json.dump(profile_data, f, indent=2)

            logger.info(
                f"Saved profile {profile_name} for {module_name} to {profile_path}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to save profile {profile_name} for {module_name}: {e}"
            )
            return False

    def list_profiles(self, module_name: str) -> list[str]:
        """
        List all available profiles for a module.

        Args:
            module_name: Name of the module

        Returns:
            List of profile names (without .json extension)
        """
        module_dir = self.profiles_dir / module_name

        if not module_dir.exists():
            return ["default"]  # Return default if no profiles directory exists

        profiles = []
        for profile_file in module_dir.glob("*.json"):
            profile_name = profile_file.stem
            profiles.append(profile_name)

        # Ensure "default" is always in the list
        if "default" not in profiles:
            profiles.insert(0, "default")

        return sorted(profiles)

    def delete_profile(self, module_name: str, profile_name: str) -> bool:
        """
        Delete a profile.

        Args:
            module_name: Name of the module
            profile_name: Name of the profile to delete

        Returns:
            True if successful, False otherwise
        """
        # Prevent deletion of default profile
        if profile_name == "default":
            logger.warning(f"Cannot delete default profile for {module_name}")
            return False

        profile_path = self.get_profile_path(module_name, profile_name)

        if not profile_path.exists():
            logger.warning(f"Profile {profile_name} for {module_name} does not exist")
            return False

        try:
            profile_path.unlink()
            logger.info(f"Deleted profile {profile_name} for {module_name}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to delete profile {profile_name} for {module_name}: {e}"
            )
            return False

    def profile_exists(self, module_name: str, profile_name: str) -> bool:
        """
        Check if a profile exists.

        Args:
            module_name: Name of the module
            profile_name: Name of the profile

        Returns:
            True if profile exists, False otherwise
        """
        profile_path = self.get_profile_path(module_name, profile_name)
        return profile_path.exists()

    def create_default_profile(
        self,
        module_name: str,
        config_dict: dict[str, Any],
        description: str | None = None,
    ) -> bool:
        """
        Create or update the default profile for a module.

        Args:
            module_name: Name of the module
            config_dict: Configuration dictionary with default values
            description: Optional description

        Returns:
            True if successful, False otherwise
        """
        return self.save_profile(
            module_name,
            "default",
            config_dict,
            description or f"Default profile for {module_name} with sensible defaults",
        )

    def export_profile(
        self, module_name: str, profile_name: str, export_path: Path
    ) -> bool:
        """
        Export a profile to a specific location.

        Args:
            module_name: Name of the module
            profile_name: Name of the profile to export
            export_path: Path where to export the profile

        Returns:
            True if successful, False otherwise
        """
        profile_path = self.get_profile_path(module_name, profile_name)

        if not profile_path.exists():
            logger.warning(f"Profile {profile_name} for {module_name} does not exist")
            return False

        try:
            shutil.copy2(profile_path, export_path)
            logger.info(
                f"Exported profile {profile_name} for {module_name} to {export_path}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to export profile {profile_name} for {module_name}: {e}"
            )
            return False

    def import_profile(
        self,
        module_name: str,
        profile_name: str,
        import_path: Path,
        overwrite: bool = False,
    ) -> bool:
        """
        Import a profile from a specific location.

        Args:
            module_name: Name of the module
            profile_name: Name for the imported profile
            import_path: Path to the profile file to import
            overwrite: Whether to overwrite existing profile

        Returns:
            True if successful, False otherwise
        """
        if not import_path.exists():
            logger.error(f"Import path {import_path} does not exist")
            return False

        profile_path = self.get_profile_path(module_name, profile_name)

        # Check if profile already exists
        if profile_path.exists() and not overwrite:
            logger.warning(
                f"Profile {profile_name} for {module_name} already exists. Use overwrite=True to replace."
            )
            return False

        try:
            # Validate JSON before copying
            with open(import_path, "r") as f:
                json.load(f)  # Validate JSON

            shutil.copy2(import_path, profile_path)
            logger.info(
                f"Imported profile {profile_name} for {module_name} from {import_path}"
            )
            return True
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in import file {import_path}: {e}")
            return False
        except Exception as e:
            logger.error(
                f"Failed to import profile {profile_name} for {module_name}: {e}"
            )
            return False

    def rename_profile(self, module_name: str, old_name: str, new_name: str) -> bool:
        """
        Rename a profile.

        Args:
            module_name: Name of the module
            old_name: Current profile name
            new_name: New profile name

        Returns:
            True if successful, False otherwise
        """
        # Prevent renaming default profile
        if old_name == "default":
            logger.warning(f"Cannot rename default profile for {module_name}")
            return False

        old_path = self.get_profile_path(module_name, old_name)
        new_path = self.get_profile_path(module_name, new_name)

        if not old_path.exists():
            logger.warning(f"Profile {old_name} for {module_name} does not exist")
            return False

        if new_path.exists():
            logger.warning(f"Profile {new_name} for {module_name} already exists")
            return False

        try:
            old_path.rename(new_path)
            logger.info(f"Renamed profile {old_name} to {new_name} for {module_name}")
            return True
        except Exception as e:
            logger.error(
                f"Failed to rename profile {old_name} to {new_name} for {module_name}: {e}"
            )
            return False


# Global profile manager instance
_profile_manager: ProfileManager | None = None


def get_profile_manager() -> ProfileManager:
    """Get the global ProfileManager instance."""
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager()
    return _profile_manager
