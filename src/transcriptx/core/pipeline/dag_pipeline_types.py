"""Shared types for DAG module execution outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional


@dataclass
class ModuleExecOutcome:
    """Result of running or skipping a single module. No side effects."""

    status: Literal["success", "skipped", "failed", "blocked"]
    module_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    # None = never started; measured non-negative ms (including genuine 0) when started.
    duration_ms: Optional[float] = None
    used_cache: bool = False
    skip_reason: Optional[str] = None
    module_run: Any = None
    module_started_at: Optional[str] = None
