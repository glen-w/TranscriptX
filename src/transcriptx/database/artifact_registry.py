"""
Artifact registry for module outputs.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.path_utils import get_transcript_dir
from transcriptx.database import get_session
from transcriptx.database.repositories import ArtifactIndexRepository

logger = get_logger()


def _file_hash(path: Path) -> str:
    hash_obj = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def _artifact_role(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/")
    if "/data/global/" in normalized or "/charts/global/" in normalized:
        return "primary"
    if "/data/" in normalized and "/data/speakers/" not in normalized:
        return "primary"
    if "/charts/" in normalized and "/charts/speakers/" not in normalized:
        return "primary"
    if "/data/speakers/" in normalized or "/charts/speakers/" in normalized:
        return "intermediate"
    if "/debug/" in normalized:
        return "debug"
    if "/export/" in normalized or "/exports/" in normalized:
        return "export"
    return "intermediate"


class ArtifactRegistry:
    """Register file artifacts in the database."""

    def __init__(self) -> None:
        self.session = get_session()
        self.repo = ArtifactIndexRepository(self.session)

    def register_module_artifacts(
        self,
        transcript_path: str,
        module_name: str,
        module_run_id: int,
        transcript_file_id: int,
    ) -> List[Dict[str, Any]]:
        output_root = Path(get_transcript_dir(transcript_path))
        module_dir = output_root / module_name
        if not module_dir.exists():
            return []

        artifacts: List[Dict[str, Any]] = []
        for file_path in module_dir.rglob("*"):
            if not file_path.is_file():
                continue
            relative_path = file_path.relative_to(output_root)
            artifact_key = str(relative_path).replace("\\", "/")
            artifact_type = (
                file_path.suffix.replace(".", "") if file_path.suffix else None
            )
            artifact_role = _artifact_role(artifact_key)
            content_hash = _file_hash(file_path)

            self.repo.create_artifact(
                module_run_id=module_run_id,
                transcript_file_id=transcript_file_id,
                artifact_key=artifact_key,
                relative_path=str(relative_path),
                artifact_root=str(output_root),
                artifact_type=artifact_type,
                artifact_role=artifact_role,
                content_hash=content_hash,
            )

            artifacts.append(
                {
                    "artifact_key": artifact_key,
                    "relative_path": str(relative_path),
                    "artifact_root": str(output_root),
                    "artifact_type": artifact_type,
                    "artifact_role": artifact_role,
                    "content_hash": content_hash,
                }
            )

        self.session.commit()
        logger.info(f"✅ Registered {len(artifacts)} artifacts for {module_name}")
        return artifacts

    def register_speaker_map_artifact(
        self,
        transcript_path: str,
        speaker_map_path: str,
        transcript_file_id: int,
    ) -> Dict[str, Any]:
        output_root = Path(get_transcript_dir(transcript_path))
        file_path = Path(speaker_map_path)
        if not file_path.exists():
            return {}
        relative_path = file_path.relative_to(output_root)
        artifact_key = str(relative_path).replace("\\", "/")
        content_hash = _file_hash(file_path)
        self.repo.create_artifact(
            module_run_id=None,
            transcript_file_id=transcript_file_id,
            artifact_key=artifact_key,
            relative_path=str(relative_path),
            artifact_root=str(output_root),
            artifact_type=file_path.suffix.replace(".", ""),
            artifact_role="sidecar",
            content_hash=content_hash,
        )
        self.session.commit()
        return {
            "artifact_key": artifact_key,
            "relative_path": str(relative_path),
            "artifact_root": str(output_root),
            "artifact_type": file_path.suffix.replace(".", ""),
            "artifact_role": "sidecar",
            "content_hash": content_hash,
        }
