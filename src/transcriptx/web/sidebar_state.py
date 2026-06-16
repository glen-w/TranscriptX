"""Derived sidebar state and transitional expander/backfill helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from transcriptx.web.state import (
    TX_NAV_EXPANDER_CONFIG,
    TX_NAV_EXPANDER_TOOLS,
    TX_NAV_EXPANDER_VIEW,
    TX_NAV_EXPANDER_WORKFLOW,
    TX_NAV_PREV_SHOULD_PRIORITIZE_VIEW,
    TX_NAV_SIDEBAR_SEEDED,
)


@dataclass(frozen=True)
class SidebarDerivedState:
    prioritize_view: bool


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


def derive_sidebar_state(session_state: dict[str, Any]) -> SidebarDerivedState:
    subject_id = session_state.get("subject_id")
    if not subject_id:
        return SidebarDerivedState(prioritize_view=False)
    if session_state.get("subject_type") == "group":
        return SidebarDerivedState(prioritize_view=True)
    return SidebarDerivedState(prioritize_view=bool(session_state.get("run_id")))


def apply_transitional_sidebar_backfill(
    session_state: dict[str, Any], *, prioritize_view: bool
) -> None:
    """
    Transitional helper for legacy expander keys only.

    This helper intentionally writes only pre-existing legacy sidebar keys.
    """
    prev_prioritize = session_state.get(TX_NAV_PREV_SHOULD_PRIORITIZE_VIEW, False)
    if not session_state.get(TX_NAV_SIDEBAR_SEEDED):
        session_state[TX_NAV_EXPANDER_WORKFLOW] = not prioritize_view
        session_state[TX_NAV_EXPANDER_VIEW] = prioritize_view
        session_state[TX_NAV_EXPANDER_TOOLS] = False
        session_state[TX_NAV_EXPANDER_CONFIG] = False
        session_state[TX_NAV_SIDEBAR_SEEDED] = True
    elif not prev_prioritize and prioritize_view:
        session_state[TX_NAV_EXPANDER_VIEW] = True
        session_state[TX_NAV_EXPANDER_WORKFLOW] = False

    if TX_NAV_EXPANDER_WORKFLOW not in session_state:
        session_state[TX_NAV_EXPANDER_WORKFLOW] = not prioritize_view
    if TX_NAV_EXPANDER_VIEW not in session_state:
        session_state[TX_NAV_EXPANDER_VIEW] = prioritize_view
    if TX_NAV_EXPANDER_TOOLS not in session_state:
        session_state[TX_NAV_EXPANDER_TOOLS] = False
    if TX_NAV_EXPANDER_CONFIG not in session_state:
        session_state[TX_NAV_EXPANDER_CONFIG] = False

    session_state[TX_NAV_PREV_SHOULD_PRIORITIZE_VIEW] = prioritize_view
