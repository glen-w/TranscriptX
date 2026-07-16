"""
Run discovery service for the Web UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from transcriptx.core.utils.paths import OUTPUTS_DIR, GROUP_OUTPUTS_DIR
from transcriptx.core.utils.run_identity import run_summary_newest_key
from transcriptx.web.services.run_visibility import has_user_artifacts, is_viewable_run


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    run_root: Path
    last_updated: Optional[float]
    mtime_ns: Optional[int] = None


class RunIndex:
    """Resolve run roots and list runs for a scope."""

    @staticmethod
    def _has_user_artifacts(run_dir: Path) -> bool:
        return has_user_artifacts(run_dir)

    @staticmethod
    def _is_viewable_run(run_dir: Path) -> bool:
        """Only expose runs that produced at least one user-visible artifact."""
        return is_viewable_run(run_dir)

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

        if not base_dir.exists() or base_dir.is_file():
            return []

        runs: List[RunSummary] = []
        for run_dir in base_dir.iterdir():
            if not run_dir.is_dir() or run_dir.name.startswith("."):
                continue
            if not RunIndex._is_viewable_run(run_dir):
                continue
            mtime: Optional[float] = None
            mtime_ns: Optional[int] = None
            try:
                st = run_dir.lstat()
                mtime = float(st.st_mtime)
                mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
            except Exception:
                mtime = None
                mtime_ns = None
            runs.append(
                RunSummary(
                    run_id=run_dir.name,
                    run_root=run_dir,
                    last_updated=mtime,
                    mtime_ns=mtime_ns,
                )
            )
        runs.sort(key=run_summary_newest_key, reverse=True)
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
