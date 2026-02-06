"""
Group output service for group aggregation.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.utils.path_utils import get_group_output_dir  # type: ignore[import]
from transcriptx.core.utils.artifact_writer import write_text  # type: ignore[import]
from transcriptx.io import save_json, save_csv  # type: ignore[import]
from transcriptx.core.utils.logger import get_logger  # type: ignore[import]
from importlib import metadata

logger = get_logger()


def _resolve_version() -> Optional[str]:
    try:
        return metadata.version("transcriptx")
    except Exception:
        return None


class GroupOutputService:
    """
    Service for writing group-level outputs.

    Scaffolds the standard group output structure but keeps outputs minimal.
    """

    def __init__(
        self,
        group_uuid: str,
        run_id: str,
        output_dir: Optional[str] = None,
        scaffold_by_session: bool = True,
        scaffold_by_speaker: bool = True,
        scaffold_comparisons: bool = True,
    ):
        self.group_uuid = group_uuid
        self.run_id = run_id
        self.base_dir = Path(output_dir or get_group_output_dir(group_uuid, run_id))
        self._ensure_structure(
            scaffold_by_session=scaffold_by_session,
            scaffold_by_speaker=scaffold_by_speaker,
            scaffold_comparisons=scaffold_comparisons,
        )

    def _ensure_structure(
        self,
        scaffold_by_session: bool,
        scaffold_by_speaker: bool,
        scaffold_comparisons: bool,
    ) -> None:
        folders = [self.base_dir, self.base_dir / "combined"]
        if scaffold_by_session:
            folders.append(self.base_dir / "by_session")
        if scaffold_by_speaker:
            folders.append(self.base_dir / "by_speaker")
        if scaffold_comparisons:
            folders.append(self.base_dir / "comparisons")
        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)

    def save_summary(self, text: str) -> str:
        path = self.base_dir / "summary.txt"
        write_text(path, text)
        logger.debug(f"Saved group summary to {path}")
        return str(path)

    def save_session_table(self, rows: List[Dict[str, Any]]) -> str:
        path = self.base_dir / "session_table.csv"
        save_csv(rows, str(path))
        logger.debug(f"Saved session table to {path}")
        return str(path)

    def save_combined_json(self, data: Dict[str, Any], name: str) -> str:
        path = self.base_dir / "combined" / f"{name}.json"
        save_json(data, str(path))
        logger.debug(f"Saved combined JSON to {path}")
        return str(path)

    def save_combined_csv(self, rows: List[Dict[str, Any]], name: str) -> str:
        path = self.base_dir / "combined" / f"{name}.csv"
        save_csv(rows, str(path))
        logger.debug(f"Saved combined CSV to {path}")
        return str(path)

    def write_group_run_metadata(
        self,
        *,
        group_uuid: str,
        group_name_at_run: Optional[str],
        group_key: Optional[str],
        member_transcript_ids: List[int],
        member_display_names: Optional[List[str]],
        selected_modules: List[str],
    ) -> str:
        payload = {
            "schema_version": 1,
            "group_uuid": group_uuid,
            "group_name_at_run": group_name_at_run,
            "group_key": group_key,
            "member_transcript_ids": list(member_transcript_ids),
            "member_display_names": list(member_display_names or []),
            "member_count": len(member_transcript_ids),
            "selected_modules": list(selected_modules),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "run_id": self.run_id,
            "tx_version": _resolve_version(),
        }
        path = self.base_dir / "group_run_metadata.json"
        save_json(payload, str(path))
        logger.debug(f"Saved group run metadata to {path}")
        return str(path)

    def write_group_manifest(
        self,
        group_id: str,
        group_key: str,
        transcript_file_uuids: List[str],
        transcript_paths: List[str],
        run_id: str,
    ) -> str:
        payload = {
            "group_id": group_id,
            "group_key": group_key,
            "transcript_file_uuids": list(transcript_file_uuids),
            "transcript_ids": list(transcript_paths),
            "run_id": run_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
        path = self.base_dir / "group_manifest.json"
        save_json(payload, str(path))
        logger.debug(f"Saved group manifest to {path}")
        return str(path)
