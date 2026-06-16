from __future__ import annotations

from transcriptx.core.pipeline.contracts import ErrorKind, PersistenceOutcome
from transcriptx.core.pipeline.ports import RunStateStore
from transcriptx.core.utils.paths import PROCESSING_STATE_FILE
from transcriptx.core.utils.processing_state import (
    find_processed_entry_for_path,
    load_processing_state,
    save_processing_state,
)
from transcriptx.core.utils.state_schema import update_analysis_state


class FileRunStateStore(RunStateStore):
    def update(self, pipeline_results):
        try:
            transcript_path = pipeline_results.get("transcript_path")
            if not PROCESSING_STATE_FILE.exists() or not transcript_path:
                return PersistenceOutcome(
                    name="processing_state", success=True, severity="optional"
                )
            state = load_processing_state()
            key, entry = find_processed_entry_for_path(transcript_path, state=state)
            if key is None or entry is None:
                return PersistenceOutcome(
                    name="processing_state", success=True, severity="optional"
                )
            state["processed_files"][key] = update_analysis_state(
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
