"""
Run controller. Lists runs, reads manifests. Reuses output structure from core.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from transcriptx.app.models.results import RunSummary
from transcriptx.app.models.errors import ArtifactReadError
from transcriptx.core.pipeline.manifest_loader import (
    load_artifact_manifest,
    load_run_results,
    load_run_manifest,
)
from transcriptx.core.pipeline.run_outcome_truth import project_canonical_outcomes
from transcriptx.core.utils.paths import OUTPUTS_DIR


def _load_manifest(run_dir: Path) -> dict | None:
    """Load manifest from run dir. Manifest is authoritative when present."""
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        try:
            return load_artifact_manifest(manifest_path)
        except Exception:
            pass
    tx_manifest = run_dir / ".transcriptx" / "manifest.json"
    if tx_manifest.exists():
        try:
            return load_run_manifest(tx_manifest)
        except Exception:
            pass
    return None


def _load_run_results_safe(run_dir: Path) -> dict | None:
    path = run_dir / "run_results.json"
    if not path.exists():
        return None
    try:
        return load_run_results(path)
    except Exception:
        return None


def _summary_status_from_outcomes(run_results: dict | None) -> tuple[str, list[str]]:
    """
    Build run summary status/modules from canonical truth projection.

    Returns (status, selected_modules).

    Requirement/policy skips are intentional non-runs (e.g. multi-speaker
    modules on a single-speaker transcript). Those do not make the run
    ``partial`` when every attempted module succeeded. ``partial`` is reserved
    for mixed failure/block outcomes (or unresolved enabled modules).
    """
    if not run_results:
        return "completed", []
    if str(run_results.get("run_status") or "").strip().lower() == "running":
        modules = [
            str(m)
            for m in (run_results.get("modules_enabled") or [])
            if m
        ]
        return "running", modules
    rows = project_canonical_outcomes(run_results)
    statuses = {row.status for row in rows}
    modules = [row.module_id for row in rows if row.status != "requested"]
    if "failed" in statuses and "succeeded" not in statuses:
        return "failed", modules
    if "failed" in statuses or "blocked" in statuses or "enabled" in statuses:
        return "partial", modules
    return "completed", modules


class RunController:
    """Orchestrates run discovery and manifest reading. No prompts, no prints."""

    def list_recent_runs(self, limit: int = 20) -> list[RunSummary]:
        """List recent runs across all transcripts. Manifest is authoritative when present."""
        base = Path(OUTPUTS_DIR)
        if not base.exists():
            return []
        runs: list[tuple[float, Path, str | None]] = []
        for slug_dir in base.iterdir():
            if not slug_dir.is_dir() or slug_dir.name.startswith("."):
                continue
            for run_dir in slug_dir.iterdir():
                if not run_dir.is_dir() or run_dir.name.startswith("."):
                    continue
                try:
                    mtime = run_dir.stat().st_mtime
                    manifest = _load_manifest(run_dir)
                    transcript_path = None
                    if manifest:
                        if isinstance(manifest.get("run_metadata"), dict):
                            meta = manifest["run_metadata"]
                            transcript_path = meta.get("transcript_path")
                        if not transcript_path and "transcript_path" in manifest:
                            transcript_path = manifest.get("transcript_path")
                        if not transcript_path and isinstance(
                            manifest.get("run_metadata"), dict
                        ):
                            transcript_path = manifest["run_metadata"].get(
                                "transcript_key"
                            )
                    if not transcript_path:
                        transcript_path = str(slug_dir)
                    runs.append((mtime, run_dir, transcript_path))
                except Exception:
                    continue
        runs.sort(key=lambda x: x[0], reverse=True)
        result = []
        for mtime, run_dir, transcript_path in runs[:limit]:
            manifest = _load_manifest(run_dir)
            created_at = datetime.fromtimestamp(mtime)
            selected_modules = []
            profile_name = None
            status = "completed"
            duration_seconds = None
            warnings_count = None
            run_results = _load_run_results_safe(run_dir)
            rr_status, rr_modules = _summary_status_from_outcomes(run_results)
            if rr_modules:
                selected_modules = rr_modules
            status = rr_status
            if manifest and isinstance(manifest.get("run_metadata"), dict):
                meta = manifest["run_metadata"]
                if not selected_modules:
                    selected_modules = (
                        meta.get("modules_run") or meta.get("modules_enabled") or []
                    )
                profile_name = meta.get("profile")
                duration_seconds = meta.get("duration")
                warnings_count = meta.get("warnings_count")
            result.append(
                RunSummary(
                    run_dir=run_dir,
                    transcript_path=Path(transcript_path or ""),
                    run_id=run_dir.name,
                    created_at=created_at,
                    selected_modules=selected_modules,
                    profile_name=profile_name,
                    manifest_path=run_dir / "manifest.json",
                    status=status,
                    duration_seconds=duration_seconds,
                    warnings_count=warnings_count,
                )
            )
        return result

    def get_run_manifest(self, run_dir: Path) -> dict:
        """Get manifest for a run. Raises ArtifactReadError if not found."""
        manifest = _load_manifest(Path(run_dir))
        if manifest is None:
            raise ArtifactReadError(f"No manifest found in {run_dir}")
        return manifest

    def list_artifacts(self, run_dir: Path) -> list[dict]:
        """List artifacts from run manifest."""
        try:
            manifest = _load_manifest(Path(run_dir))
            if manifest and "artifacts" in manifest:
                return list(manifest["artifacts"])
            return []
        except Exception:
            return []
