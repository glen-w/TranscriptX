"""
Diagnostics controller. Doctor, dependency status. No prompts, no prints.
"""

from __future__ import annotations

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.run_manifest import get_dependency_versions


class DiagnosticsController:
    """Read-only diagnostics. No prompts, no prints."""

    def get_doctor_report(self) -> dict:
        """Environment and configuration diagnostics (equivalent to transcriptx doctor)."""
        config = get_config()
        return {
            "config_snapshot_available": hasattr(config, "to_dict"),
            "dependency_versions": get_dependency_versions(),
        }
