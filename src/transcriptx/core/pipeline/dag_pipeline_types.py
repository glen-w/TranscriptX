"""Shared types for DAG module execution outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional


@dataclass
class ModuleExecOutcome:
    """Result of running or skipping a single module. No side effects."""

    status: Literal["success", "skipped", "failed"]
    module_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    used_cache: bool = False
    skip_reason: Optional[str] = None
    module_run: Any = None
    module_started_at: Optional[str] = None
