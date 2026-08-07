"""Persist pipeline run artifacts and state layers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from transcriptx.core.pipeline.contracts import (
    ErrorKind,
    PersistenceOutcome,
    RunConfigSnapshot,
)
from transcriptx.core.pipeline.pipeline_write_phases import (
    persist_canonical_results_and_artifacts,
)
from transcriptx.core.utils.paths import PROCESSING_STATE_FILE
from transcriptx.core.utils.processing_state import (
    find_processed_entry_for_path,
    load_processing_state,
    save_processing_state,
)
from transcriptx.core.utils.run_manifest import (
    create_run_manifest,
    save_run_manifest,
    compute_file_hash,
)
from transcriptx.core.utils.run_report import save_run_report
from transcriptx.core.utils.state_schema import update_analysis_state


class PersistenceLayer:
    def persist_run_outputs(
        self,
        *,
        output_dir: str,
        run_id: str,
        transcript_key: str,
        selected_modules: List[str],
        results: Dict[str, Any],
        on_event: Any = None,
    ) -> PersistenceOutcome:
        try:
            persist_canonical_results_and_artifacts(
                run_dir=Path(output_dir),
                run_id=run_id,
                transcript_key=transcript_key,
                modules_enabled=selected_modules,
                results=results,
                on_event=on_event,
            )
            return PersistenceOutcome(
                name="canonical_results", success=True, severity="required"
            )
        except Exception as e:
            return PersistenceOutcome(
                name="canonical_results",
                success=False,
                severity="required",
                error_kind=ErrorKind.PERSISTENCE,
                error_message=str(e),
            )

    def persist_processing_state(
        self, transcript_path: str, pipeline_results: Dict[str, Any]
    ) -> PersistenceOutcome:
        try:
            if not PROCESSING_STATE_FILE.exists():
                return PersistenceOutcome(
                    name="processing_state", success=True, severity="optional"
                )
            state = load_processing_state()
            file_key, entry = find_processed_entry_for_path(
                transcript_path, state=state
            )
            if file_key is None or entry is None:
                return PersistenceOutcome(
                    name="processing_state", success=True, severity="optional"
                )
            state["processed_files"][file_key] = update_analysis_state(
                entry, pipeline_results
            )
            save_processing_state(state)
            return PersistenceOutcome(
                name="processing_state", success=True, severity="required"
            )
        except Exception as e:
            return PersistenceOutcome(
                name="processing_state",
                success=False,
                severity="required",
                error_kind=ErrorKind.PERSISTENCE,
                error_message=str(e),
            )

    def persist_run_report(
        self, run_report: Any, output_dir: str
    ) -> PersistenceOutcome:
        try:
            save_run_report(run_report, output_dir)
            return PersistenceOutcome(
                name="run_report", success=True, severity="required"
            )
        except Exception as e:
            return PersistenceOutcome(
                name="run_report",
                success=False,
                severity="required",
                error_kind=ErrorKind.PERSISTENCE,
                error_message=str(e),
            )

    def persist_manifest(
        self,
        *,
        output_dir: str,
        selected_modules: List[str],
        transcript_path: str,
        source_basename: str,
        run_id: str,
        transcript_key: str,
        transcript_identity_hash: str,
        transcript_content_hash_full: str,
        transcript_file_hash: str | None,
        canonical_schema_version: int,
        config_snapshot: RunConfigSnapshot,
        draft_override_used: bool,
    ) -> PersistenceOutcome:
        try:
            artifact_index: List[Dict[str, Any]] = []
            output_root = Path(output_dir)
            if output_root.exists():
                for file_path in sorted(output_root.rglob("*")):
                    if file_path.is_file() and file_path.name != "manifest.json":
                        artifact_index.append(
                            {
                                "path": file_path.relative_to(output_root).as_posix(),
                                "checksum": compute_file_hash(file_path),
                            }
                        )
            manifest = create_run_manifest(
                transcript_hash=transcript_file_hash or transcript_key,
                transcript_file_hash=transcript_file_hash,
                transcript_identity_hash=transcript_identity_hash,
                transcript_content_hash_full=transcript_content_hash_full,
                canonical_schema_version=canonical_schema_version,
                selected_modules=selected_modules,
                artifact_index=artifact_index,
                config_hash=config_snapshot.config_hash,
                config_effective_path=".transcriptx/run_config_effective.json",
                config_override_path=(
                    ".transcriptx/run_config_override.json"
                    if draft_override_used
                    else None
                ),
                config_schema_version=config_snapshot.schema_version,
                config_source=config_snapshot.config_source,
                transcript_path=transcript_path,
                source_basename=source_basename,
                source_path=transcript_path,
                run_id=run_id,
            )
            save_run_manifest(manifest, output_dir)
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
