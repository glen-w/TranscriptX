"""
Run controller. Lists runs, reads manifests. Reuses output structure from core.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from transcriptx.app.models.results import RunSummary
from transcriptx.app.models.errors import ArtifactReadError
from transcriptx.core.utils.paths import OUTPUTS_DIR


def _load_manifest(run_dir: Path) -> dict | None:
    """Load manifest from run dir. Manifest is authoritative when present."""
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        try:
            import json

            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    tx_manifest = run_dir / ".transcriptx" / "manifest.json"
    if tx_manifest.exists():
        try:
            import json

            return json.loads(tx_manifest.read_text(encoding="utf-8"))
        except Exception:
            pass
    return None


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
            if manifest and isinstance(manifest.get("run_metadata"), dict):
                meta = manifest["run_metadata"]
                selected_modules = (
                    meta.get("modules_run") or meta.get("modules_enabled") or []
                )
                profile_name = meta.get("profile")
                status = meta.get("status", "completed")
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
