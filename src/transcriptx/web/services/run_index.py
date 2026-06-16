"""
Run discovery service for the Web UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from transcriptx.core.utils.paths import OUTPUTS_DIR, GROUP_OUTPUTS_DIR
from transcriptx.core.pipeline.manifest_loader import load_artifact_manifest


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    run_root: Path
    last_updated: Optional[float]


class RunIndex:
    """Resolve run roots and list runs for a scope."""

    @staticmethod
    def _has_user_artifacts(run_dir: Path) -> bool:
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.is_file():
            return False
        try:
            manifest = load_artifact_manifest(manifest_path)
        except Exception:
            return False
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return False
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            rel_path = str(artifact.get("rel_path") or "")
            if (
                rel_path
                and not rel_path.startswith(".transcriptx/")
                and rel_path not in {"run_results.json", "run_report.json"}
            ):
                return True
        return False

    @staticmethod
    def _is_viewable_run(run_dir: Path) -> bool:
        """Only expose runs that produced at least one user-visible artifact."""
        return RunIndex._has_user_artifacts(run_dir)

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
