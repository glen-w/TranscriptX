"""Apply profile data and load module profiles onto TranscriptXConfig."""

from __future__ import annotations

import os
from typing import Any

from transcriptx.core.config import (
    get_profile_target_adapter,
    iter_runtime_profile_target_adapters,
)


def apply_profile_to_config(config_obj: Any, profile_data: dict[str, Any]) -> None:
    """
    Apply profile data to a config object.

    Args:
        config_obj: The config dataclass instance to update
        profile_data: Dictionary with profile settings
    """
    for key, value in profile_data.items():
        if hasattr(config_obj, key):
            if isinstance(value, list) and len(value) == 2:
                try:
                    if all(isinstance(x, (int, float)) for x in value):
                        value = tuple(value)
                except (ValueError, TypeError):
                    pass
            setattr(config_obj, key, value)
    if hasattr(config_obj, "validate"):
        config_obj.validate()


def load_module_profiles(config: Any) -> None:
    """
    Load active profiles for each module onto ``config``.

    Profile settings override defaults and file settings but not environment variables.
    If a profile doesn't exist, the default values from the dataclass are used.
    """
    from transcriptx.core.utils.profile_manager import get_profile_manager

    profile_manager = get_profile_manager()

    for adapter in iter_runtime_profile_target_adapters():
        active_profile_name = adapter.get_active_profile_name(config)
        profile_data = profile_manager.load_profile(
            adapter.target_id, active_profile_name
        )
        config_obj = adapter.get_target_config_obj(config)
        if config_obj is not None and profile_data and "config" in profile_data:
            apply_profile_to_config(config_obj, profile_data["config"])

    env_acts_model = os.getenv("TRANSCRIPTX_ACTS_MODEL")
    if env_acts_model:
        acts_adapter = get_profile_target_adapter("acts")
        acts_cfg = acts_adapter.get_target_config_obj(config) if acts_adapter else None
        if acts_cfg is not None:
            setattr(acts_cfg, "ml_model_name", env_acts_model)
