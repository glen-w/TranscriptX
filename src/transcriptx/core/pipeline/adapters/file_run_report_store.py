from __future__ import annotations

from typing import Any

from transcriptx.core.pipeline.contracts import ErrorKind, PersistenceOutcome
from transcriptx.core.pipeline.ports import RunReportStore
from transcriptx.core.utils.run_report import save_run_report


class FileRunReportStore(RunReportStore):
    def save(self, output_dir: str, run_report: Any) -> PersistenceOutcome:
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
