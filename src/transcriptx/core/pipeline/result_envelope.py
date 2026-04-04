"""
Stable envelope for per-transcript analysis results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class PerTranscriptResult:
    """Stable envelope for per-transcript analysis results."""

    transcript_path: str
    transcript_key: str
    run_id: str
    order_index: int
    output_dir: str
    module_results: Dict[str, Any]
    modules_run: List[str] = field(default_factory=list)
    skipped_modules: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transcript_path": self.transcript_path,
            "transcript_key": self.transcript_key,
            "run_id": self.run_id,
            "order_index": self.order_index,
            "output_dir": self.output_dir,
            "module_results": self.module_results,
            "modules_run": list(self.modules_run),
            "skipped_modules": list(self.skipped_modules),
        }
