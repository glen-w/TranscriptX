"""
Settings controller. Read config and storage roots. No prompts, no prints.
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.paths import PATHS


class SettingsController:
    """Orchestrates config and settings. No prompts, no prints."""

    def get_effective_config(self) -> dict:
        """Return effective config as nested dict."""
        config = get_config()
        if hasattr(config, "to_dict"):
            return config.to_dict()
        return {}

    def get_storage_roots(self) -> dict[str, Path]:
        """Return storage root paths."""
        ps = PATHS
        return {
            "recordings_dir": ps.recordings_dir,
            "transcripts_dir": ps.transcripts_dir,
            "outputs_dir": ps.outputs_dir,
            "config_dir": ps.config_dir,
            "state_dir": ps.state_dir,
        }
