"""Filesystem adapter for run config snapshots."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.pipeline.contracts import ErrorKind, PersistenceOutcome
from transcriptx.core.pipeline.ports import ConfigSnapshotStore
from transcriptx.core.utils.artifact_writer import write_json


class FileConfigSnapshotStore(ConfigSnapshotStore):
    def save(self, output_dir: str, payload):
        try:
            path = Path(output_dir) / ".transcriptx" / "run_config_snapshot.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            write_json(path, payload, indent=2, ensure_ascii=False)
            return PersistenceOutcome(
                name="config_snapshot", success=True, severity="optional"
            )
        except Exception as e:
            return PersistenceOutcome(
                name="config_snapshot",
                success=False,
                severity="optional",
                error_kind=ErrorKind.PERSISTENCE,
                error_message=str(e),
            )
