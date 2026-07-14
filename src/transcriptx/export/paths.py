"""Pure artifact path resolution for export (no web service imports)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from transcriptx.web.models.artifact import Artifact


def artifact_base_path(run_root: Path, artifact: Artifact) -> Path:
    if artifact.storage_root:
        return Path(artifact.storage_root).resolve()
    return run_root.resolve()


def resolve_safe_path(base_dir: Path, rel_path: str) -> Optional[Path]:
    if ".." in rel_path.split("/"):
        return None
    candidate = (base_dir / rel_path).resolve()
    try:
        if not candidate.is_relative_to(base_dir.resolve()):
            return None
    except AttributeError:
        if not str(candidate).startswith(str(base_dir.resolve())):
            return None
    return candidate


def resolve_artifact_source_path(run_root: Path, artifact: Artifact) -> Optional[Path]:
    """Resolve and safety-check the on-disk source path for an artifact."""
    base = artifact_base_path(run_root, artifact)
    path = resolve_safe_path(base, artifact.rel_path)
    if path is None or not path.exists():
        return None
    return path
