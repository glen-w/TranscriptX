"""Structured return value from the group chart runner."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GroupChartRunResult:
    """
    Result of run_group_aggregate_charts (v1); pipeline may ignore unused fields.

    ``skipped_reason`` (when set):
    - ``no_generator``: ``agg_id`` not in the chart registry.
    - ``can_generate_false``: generator declined (empty / invalid outcome).
    - ``chart_failed``: ``generate()`` raised; see ``warnings`` (e.g. ``GROUP_CHART_FAILED``).
    """

    emitted_paths: List[Path] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    skipped_reason: Optional[str] = None
