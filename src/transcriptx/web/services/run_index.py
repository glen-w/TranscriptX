"""
Run discovery service for the Web UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from transcriptx.core.utils.paths import OUTPUTS_DIR, GROUP_OUTPUTS_DIR


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    run_root: Path
    last_updated: Optional[float]


class RunIndex:
    """Resolve run roots and list runs for a scope."""

    @staticmethod
    def list_runs(scope: Any, subject_id: Optional[str] = None) -> List[RunSummary]:
        if scope.scope_type == "transcript":
            if not subject_id:
                return []
            base_dir = Path(OUTPUTS_DIR) / subject_id
        elif scope.scope_type == "group":
            base_dir = Path(GROUP_OUTPUTS_DIR) / scope.uuid
        else:
            return []

        if not base_dir.exists():
            return []

        runs: List[RunSummary] = []
        for run_dir in base_dir.iterdir():
            if not run_dir.is_dir() or run_dir.name.startswith("."):
                continue
            try:
                mtime = run_dir.stat().st_mtime
            except Exception:
                mtime = None
            runs.append(
                RunSummary(
                    run_id=run_dir.name,
                    run_root=run_dir,
                    last_updated=mtime,
                )
            )
        runs.sort(key=lambda r: r.last_updated or 0, reverse=True)
        return runs

    @staticmethod
    def get_run_root(scope: Any, run_id: str, subject_id: Optional[str] = None) -> Path:
        if scope.scope_type == "transcript":
            if not subject_id:
                raise ValueError("subject_id (slug) is required for transcript runs.")
            return Path(OUTPUTS_DIR) / subject_id / run_id
        if scope.scope_type == "group":
            return Path(GROUP_OUTPUTS_DIR) / scope.uuid / run_id
        raise ValueError("Unsupported scope type.")
