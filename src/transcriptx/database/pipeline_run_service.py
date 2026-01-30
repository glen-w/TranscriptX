"""
Pipeline run coordination for canonical DB persistence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx import __version__
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.module_hashing import (
    compute_module_config_hash,
    compute_module_source_hash,
    compute_pipeline_config_hash,
)
from transcriptx.database import get_session
from transcriptx.database.models import PipelineRun, ModuleRun, TranscriptFile
from transcriptx.database.repositories import (
    ArtifactIndexRepository,
    ModuleRunRepository,
    PipelineRunRepository,
)
from transcriptx.database.transcript_ingestion import TranscriptIngestionService
from transcriptx.database.artifact_registry import ArtifactRegistry
from transcriptx.database.migrations import require_up_to_date_schema

logger = get_logger()


def _hash_payload(payload: Dict[str, Any]) -> str:
    serialized = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class PipelineRunCoordinator:
    """Coordinates pipeline execution with DB runs, caching, and artifacts."""

    def __init__(
        self,
        transcript_path: str,
        selected_modules: List[str],
        pipeline_config: Dict[str, Any],
        cli_args: Optional[Dict[str, Any]] = None,
        auto_import: bool = True,
        strict_db: bool = False,
        rerun_mode: str = "reuse-existing-run",
    ) -> None:
        self.transcript_path = transcript_path
        self.selected_modules = selected_modules
        self.pipeline_config = pipeline_config
        self.cli_args = cli_args or {}
        self.auto_import = auto_import
        self.strict_db = strict_db
        self.rerun_mode = rerun_mode
        self.reused_pipeline_run = False

        self.session = get_session()
        self.pipeline_repo = PipelineRunRepository(self.session)
        self.module_repo = ModuleRunRepository(self.session)
        self.artifact_repo = ArtifactIndexRepository(self.session)
        self.artifact_registry = ArtifactRegistry()
        self.ingestion_service = TranscriptIngestionService()

        self.transcript_file: Optional[TranscriptFile] = None
        self.pipeline_run: Optional[PipelineRun] = None
        self._dependency_output_hashes: Dict[str, str] = {}

    def start(self) -> PipelineRun:
        require_up_to_date_schema()
        self.transcript_file = self._get_or_import_transcript()

        pipeline_config_hash = compute_pipeline_config_hash(self.pipeline_config)
        pipeline_input_hash = _hash_payload(
            {
                "transcript_content_hash": self.transcript_file.transcript_content_hash,
                "pipeline_config_hash": pipeline_config_hash,
            }
        )

        if self.rerun_mode == "reuse-existing-run":
            cached = self.pipeline_repo.find_latest_by_input_hash(
                transcript_file_id=self.transcript_file.id,
                pipeline_input_hash=pipeline_input_hash,
            )
            if cached:
                logger.info(f"♻️ Reusing PipelineRun {cached.id}")
                self.pipeline_run = cached
                self.reused_pipeline_run = True
                return cached

        self.pipeline_run = self.pipeline_repo.create_pipeline_run(
            transcript_file_id=self.transcript_file.id,
            pipeline_version=__version__,
            pipeline_config_hash=pipeline_config_hash,
            pipeline_input_hash=pipeline_input_hash,
            cli_args_json=self.cli_args,
        )
        logger.info(f"✅ Created PipelineRun {self.pipeline_run.id}")
        return self.pipeline_run

    def _get_or_import_transcript(self) -> TranscriptFile:
        transcript_file = (
            self.session.query(TranscriptFile)
            .filter(
                TranscriptFile.file_path == str(Path(self.transcript_path).resolve())
            )
            .first()
        )
        if transcript_file:
            return transcript_file

        if not self.auto_import:
            raise FileNotFoundError(
                f"Transcript not found in DB and auto-import disabled: {self.transcript_path}"
            )

        logger.info("📥 Transcript not found in DB; importing via canonical ingestion")
        return self.ingestion_service.ingest_transcript(
            self.transcript_path,
            store_segments=False,
        )

    def begin_module_run(
        self,
        module_name: str,
        module_config: Dict[str, Any],
        dependency_names: List[str],
    ) -> tuple[Optional[ModuleRun], bool]:
        """Create ModuleRun or return cached ModuleRun if cache hit."""
        if not self.transcript_file or not self.pipeline_run:
            raise RuntimeError("Pipeline run not initialized")

        module_version = compute_module_source_hash(module_name)
        module_config_hash = compute_module_config_hash(module_name, module_config)
        dependency_fingerprints = [
            self._dependency_output_hashes.get(dep, "") for dep in dependency_names
        ]

        module_input_hash = _hash_payload(
            {
                "transcript_content_hash": self.transcript_file.transcript_content_hash,
                "module_config_hash": module_config_hash,
                "module_version": module_version,
                "dependency_fingerprints": dependency_fingerprints,
            }
        )

        cached = self.module_repo.find_cacheable_run(
            transcript_file_id=self.transcript_file.id,
            module_name=module_name,
            module_version=module_version,
            module_input_hash=module_input_hash,
        )
        if cached and self._cache_is_valid(cached):
            logger.info(f"♻️ Cache hit for {module_name}")
            cache_run = self.module_repo.create_module_run(
                pipeline_run_id=self.pipeline_run.id,
                transcript_file_id=self.transcript_file.id,
                module_name=module_name,
                module_version=module_version,
                module_config_hash=module_config_hash,
                module_input_hash=module_input_hash,
                replaces_module_run_id=None,
                is_cacheable=False,
                cache_reason="cache_hit",
            )
            self.module_repo.update_completion(
                cache_run.id,
                status="completed",
                output_hash=cached.output_hash,
                is_cacheable=False,
            )
            self._dependency_output_hashes[module_name] = cached.output_hash or ""
            return cache_run, True

        run = self.module_repo.create_module_run(
            pipeline_run_id=self.pipeline_run.id,
            transcript_file_id=self.transcript_file.id,
            module_name=module_name,
            module_version=module_version,
            module_config_hash=module_config_hash,
            module_input_hash=module_input_hash,
        )
        return run, False

    def complete_module_run(
        self,
        module_run: ModuleRun,
        module_name: str,
        duration_seconds: float,
        module_failed: bool,
        module_result: Optional[Dict[str, Any]],
    ) -> None:
        if module_failed:
            if module_result:
                module_run.outputs_json = module_result
                if isinstance(module_result, dict) and module_result.get("metrics"):
                    module_run.metrics_json = module_result.get("metrics", {})
                self.session.flush()
            self.module_repo.update_completion(
                module_run.id,
                status="failed",
                duration_seconds=duration_seconds,
                is_cacheable=False,
            )
            return

        artifacts = self.artifact_registry.register_module_artifacts(
            transcript_path=self.transcript_path,
            module_name=module_name,
            module_run_id=module_run.id,
            transcript_file_id=self.transcript_file.id,
        )
        if module_result:
            module_run.outputs_json = module_result
            if isinstance(module_result, dict) and module_result.get("metrics"):
                module_run.metrics_json = module_result.get("metrics", {})
            self.session.flush()
        output_hash = self._compute_output_hash(artifacts, module_run)
        self.module_repo.update_completion(
            module_run.id,
            status="completed",
            duration_seconds=duration_seconds,
            output_hash=output_hash,
        )
        self._dependency_output_hashes[module_name] = output_hash

    def finish(self, success: bool) -> None:
        if self.pipeline_run:
            self.pipeline_repo.update_status(
                self.pipeline_run.id, "completed" if success else "failed"
            )

    def get_cached_module_names(self) -> List[str]:
        if not self.pipeline_run:
            return []
        runs = (
            self.session.query(ModuleRun)
            .filter(ModuleRun.pipeline_run_id == self.pipeline_run.id)
            .all()
        )
        return [run.module_name for run in runs]

    def _cache_is_valid(self, cached: ModuleRun) -> bool:
        primary_artifacts = self.artifact_repo.get_primary_artifacts(cached.id)
        if not primary_artifacts:
            return False
        for artifact in primary_artifacts:
            if not artifact.artifact_root:
                continue
            resolved = Path(artifact.artifact_root) / artifact.relative_path
            if not resolved.exists():
                return False
        return True

    def _compute_output_hash(
        self, artifacts: List[Dict[str, Any]], module_run: ModuleRun
    ) -> str:
        primary = [
            artifact
            for artifact in artifacts
            if artifact.get("artifact_role") == "primary"
        ]
        if primary:
            payload = sorted(
                [
                    (artifact["artifact_key"], artifact.get("content_hash", ""))
                    for artifact in primary
                ]
            )
            serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
            return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

        fallback_payload = {
            "module": module_run.module_name,
            "module_version": module_run.module_version,
            "outputs_json": module_run.outputs_json or {},
        }
        serialized = json.dumps(fallback_payload, separators=(",", ":"), sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def close(self) -> None:
        self.ingestion_service.close()
        if self.session:
            self.session.close()
