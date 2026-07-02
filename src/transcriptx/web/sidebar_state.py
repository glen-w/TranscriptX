"""Sidebar selection state helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SidebarSelectionResult:
    subject_type: str | None
    subject_id: str | None
    run_id: str | None


def apply_sidebar_selection(
    session_state: dict[str, Any], result: SidebarSelectionResult
) -> None:
    """Apply canonical sidebar selection state in one place."""
    session_state["subject_type"] = result.subject_type
    session_state["subject_id"] = result.subject_id
    session_state["run_id"] = result.run_id
