"""
Stable envelope for per-transcript analysis results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class PerTranscriptResult:
    """Stable envelope for per-transcript analysis results."""

    transcript_path: str
    transcript_key: str
    run_id: str
    order_index: int
    output_dir: str
    module_results: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "transcript_path": self.transcript_path,
            "transcript_key": self.transcript_key,
            "run_id": self.run_id,
            "order_index": self.order_index,
            "output_dir": self.output_dir,
            "module_results": self.module_results,
        }
