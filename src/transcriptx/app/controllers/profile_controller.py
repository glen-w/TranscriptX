"""
Profile controller. List and load analysis profiles. No prompts, no prints.
"""

from __future__ import annotations

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.profile_manager import get_profile_manager


def _get_active_profile_name(module: str) -> str:
    """Get active profile name from config."""
    config = get_config()
    if module == "workflow":
        return getattr(config, "active_workflow_profile", "default")
    return getattr(config.analysis, f"active_{module}_profile", "default")


class ProfileController:
    """Orchestrates profile operations. No prompts, no prints."""

    def list_profiles(self, module: str) -> list[str]:
        """List profile names for a module."""
        pm = get_profile_manager()
        return pm.list_profiles(module)

    def get_active_profile(self, module: str) -> str:
        """Get active profile name for a module."""
        return _get_active_profile_name(module)

    def load_profile(self, module: str, name: str) -> dict:
        """Load profile config as dict."""
        pm = get_profile_manager()
        result = pm.load_profile(module, name)
        return result if result is not None else {}
