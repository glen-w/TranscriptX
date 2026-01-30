"""
Run report for execution outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from transcriptx.core.utils.artifact_writer import write_json


class ModuleResult(str, Enum):
    RUN = "RUN"
    SKIP = "SKIP"
    FAIL = "FAIL"


@dataclass
class ModuleReport:
    status: ModuleResult
    duration_seconds: Optional[float] = None
    reason: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RunReport:
    transcript_hash: str
    run_id: str
    modules: Dict[str, ModuleReport] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        modules: Dict[str, Dict[str, object]] = {}
        for name, report in self.modules.items():
            modules[name] = {
                "status": report.status.value,
                "duration_seconds": report.duration_seconds,
                "reason": report.reason,
                "error": report.error,
            }
        return {
            "transcript_hash": self.transcript_hash,
            "run_id": self.run_id,
            "modules": modules,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }

    def record_module(
        self,
        module_name: str,
        status: ModuleResult,
        duration_seconds: Optional[float] = None,
        reason: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        self.modules[module_name] = ModuleReport(
            status=status,
            duration_seconds=duration_seconds,
            reason=reason,
            error=error,
        )


def save_run_report(report: RunReport, output_dir: str | Path) -> Path:
    output_path = Path(output_dir) / ".transcriptx"
    output_path.mkdir(parents=True, exist_ok=True)
    report_path = output_path / "run_report.json"
    write_json(report_path, report.to_dict(), indent=2, ensure_ascii=False)
    return report_path
