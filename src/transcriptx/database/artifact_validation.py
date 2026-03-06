"""
Artifact validation service for DB ↔ FS integrity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set, cast

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.path_utils import (
    get_transcript_dir,
    get_canonical_base_name,
)
from transcriptx.database import get_session
from transcriptx.database.models import ArtifactIndex, ModuleRun, TranscriptFile
from transcriptx.database.artifact_registry import _file_hash

logger = get_logger()


@dataclass
class ArtifactValidationReport:
    p0_errors: List[str] = field(default_factory=list)
    p1_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    checked_files: int = 0
    checked_records: int = 0

    def exit_code(self, strict: bool = False) -> int:
        if self.p0_errors:
            return 2
        if self.p1_errors:
            return 1
        if strict and self.warnings:
            return 1
        return 0


class ArtifactValidationService:
    """Validate DB ↔ FS artifact integrity and provenance."""

    def __init__(self) -> None:
        self.session = get_session()

    def validate(
        self,
        transcript_identifier: str,
        pipeline_run_id: Optional[int] = None,
        strict: bool = False,
    ) -> ArtifactValidationReport:
        report = ArtifactValidationReport()
        transcript = self._resolve_transcript(transcript_identifier)
        if not transcript:
            report.p0_errors.append(f"Transcript not found: {transcript_identifier}")
            return report

        default_root = Path(get_transcript_dir(transcript.file_path))
        expected_records = self._load_artifact_records(transcript.id, pipeline_run_id)
        report.checked_records = len(expected_records)

        expected_by_root: dict[Path, Set[str]] = {}
        for record in expected_records:
            record_root = (
                Path(record.artifact_root) if record.artifact_root else default_root
            )
            expected_by_root.setdefault(record_root, set()).add(record.relative_path)

        file_paths_by_root: dict[Path, List[str]] = {}
        for root in expected_by_root.keys() or {default_root}:
            file_paths_by_root[root] = self._collect_files(root)
        report.checked_files = sum(len(paths) for paths in file_paths_by_root.values())

        # Missing files and hash mismatch
        for record in expected_records:
            file_path = (
                Path(record.artifact_root) if record.artifact_root else default_root
            ) / record.relative_path
            if not file_path.exists():
                report.p0_errors.append(f"Missing file: {record.relative_path}")
                continue
            if record.content_hash:
                actual_hash = _file_hash(file_path)
                if actual_hash != record.content_hash:
                    report.p1_errors.append(f"Hash mismatch: {record.relative_path}")

            if not record.module_run or not record.module_run.pipeline_run:
                report.p0_errors.append(
                    f"Broken provenance for artifact: {record.relative_path}"
                )

        # Orphan DB records (missing module run or pipeline run)
        for record in expected_records:
            if not record.module_run or not record.module_run.pipeline_run:
                report.p0_errors.append(
                    f"Orphan artifact record: {record.relative_path}"
                )

        # Role uniqueness per module_run + artifact_key
        seen_keys: Set[str] = set()
        for record in expected_records:
            key = f"{record.module_run_id}:{record.artifact_key}"
            if key in seen_keys:
                report.p0_errors.append(
                    f"Duplicate artifact key in module run: {record.artifact_key}"
                )
            seen_keys.add(key)

        # Orphan files (no DB record)
        for root, file_paths in file_paths_by_root.items():
            expected_paths = expected_by_root.get(root, set())
            orphan_files = [path for path in file_paths if path not in expected_paths]
            for orphan in orphan_files:
                report.p1_errors.append(f"Orphan file: {orphan}")

        # Warnings: naming + unknown types
        base_name = get_canonical_base_name(transcript.file_path)
        for file_paths in file_paths_by_root.values():
            for relative_path in file_paths:
                if base_name not in Path(relative_path).name:
                    report.warnings.append(f"Suspicious filename: {relative_path}")
                suffix = Path(relative_path).suffix.lower().lstrip(".")
                if suffix and suffix not in {
                    "json",
                    "csv",
                    "png",
                    "jpg",
                    "jpeg",
                    "svg",
                    "html",
                    "txt",
                }:
                    report.warnings.append(
                        f"Unrecognized artifact type: {relative_path}"
                    )

        logger.info(
            f"Artifact validation: {report.checked_records} records, {report.checked_files} files"
        )
        return report

    def _resolve_transcript(self, identifier: str) -> Optional[TranscriptFile]:
        if identifier.isdigit():
            return (
                self.session.query(TranscriptFile)
                .filter(TranscriptFile.id == int(identifier))
                .first()
            )
        if len(identifier) == 64:
            transcript = (
                self.session.query(TranscriptFile)
                .filter(TranscriptFile.transcript_content_hash == identifier)
                .first()
            )
            if transcript:
                return transcript
        path = Path(identifier)
        if path.exists():
            return (
                self.session.query(TranscriptFile)
                .filter(TranscriptFile.file_path == str(path.resolve()))
                .first()
            )
        return None

    def _load_artifact_records(
        self, transcript_file_id: int, pipeline_run_id: Optional[int]
    ) -> List[ArtifactIndex]:
        query = self.session.query(ArtifactIndex).filter(
            ArtifactIndex.transcript_file_id == transcript_file_id
        )
        if pipeline_run_id is not None:
            query = query.join(ModuleRun).filter(
                ModuleRun.pipeline_run_id == pipeline_run_id
            )
        return cast(List[ArtifactIndex], query.all())

    def _collect_files(self, artifact_root: Path) -> List[str]:
        if not artifact_root.exists():
            return []
        ignore = {".ds_store"}
        files: List[str] = []
        for file_path in artifact_root.rglob("*"):
            if not file_path.is_file():
                continue
            if ".transcriptx" in file_path.parts:
                continue
            if file_path.name.lower() in ignore:
                continue
            relative_path = file_path.relative_to(artifact_root).as_posix()
            files.append(relative_path)
        return files

    def close(self) -> None:
        if self.session:
            self.session.close()
