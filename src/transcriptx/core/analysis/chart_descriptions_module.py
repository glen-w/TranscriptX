"""Finalize-phase stub module (excluded from DAG; executed by coordinator)."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.analysis.base import AnalysisModule
from transcriptx.core.utils.module_result import build_module_result, now_iso


class ChartDescriptionsAnalysis(AnalysisModule):
    """Placeholder so the module is selectable; real work is finalize-phase."""

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.module_name = "chart_descriptions"

    def analyze(self, segments: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Should never run in the DAG when finalize_phase is honored.
        started = now_iso()
        return build_module_result(
            module_name=self.module_name,
            status="skipped",
            started_at=started,
            finished_at=now_iso(),
            metrics={"skip_reason": "finalize_phase_only"},
            payload={"finalize_phase": True},
        )
