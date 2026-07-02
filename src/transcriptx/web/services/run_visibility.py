"""Shared run visibility rules for session listing and run indexing."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.pipeline.manifest_loader import load_artifact_manifest

_INTERNAL_ARTIFACTS = frozenset({"run_results.json", "run_report.json"})


def has_user_artifacts(run_dir: Path) -> bool:
    """Return True when the run manifest lists at least one user-visible artifact."""
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
            and rel_path not in _INTERNAL_ARTIFACTS
        ):
            return True
    return False


def is_viewable_run(run_dir: Path) -> bool:
    """Return True when the run should appear in user-facing run lists."""
    return has_user_artifacts(run_dir)
