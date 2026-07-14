"""Filesystem adapter for pipeline artifact manifests."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from transcriptx.core.pipeline.contracts import ErrorKind, PersistenceOutcome
from transcriptx.core.pipeline.ports import ArtifactStore
from transcriptx.core.utils.run_manifest import compute_file_hash, save_run_manifest


class ArtifactManifestStore(ArtifactStore):
    def save_manifest(self, payload, output_dir: str) -> PersistenceOutcome:
        try:
            save_run_manifest(payload, output_dir)
            return PersistenceOutcome(
                name="manifest", success=True, severity="required"
            )
        except Exception as e:
            return PersistenceOutcome(
                name="manifest",
                success=False,
                severity="required",
                error_kind=ErrorKind.PERSISTENCE,
                error_message=str(e),
            )

    def index_artifacts(self, output_dir: str) -> List[Dict[str, str]]:
        root = Path(output_dir)
        rows: List[Dict[str, str]] = []
        if not root.exists():
            return rows
        for file_path in sorted(root.rglob("*")):
            if file_path.is_file() and file_path.name != "manifest.json":
                rows.append(
                    {
                        "path": file_path.relative_to(root).as_posix(),
                        "checksum": compute_file_hash(file_path),
                    }
                )
        return rows
