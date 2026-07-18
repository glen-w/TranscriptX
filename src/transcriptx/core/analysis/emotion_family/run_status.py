"""Run status, evaluation state, and usable_output helpers."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping, Sequence


class RunStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"


class EvaluationState(str, Enum):
    SCORED = "scored"
    SKIPPED = "skipped"
    FAILED = "failed"
    EMPTY = "empty"


class AnalyticalOutcome(str, Enum):
    NEUTRAL = "neutral"
    ABSTAINED = "abstained"
    NO_LABEL = "no_label"
    LABELED = "labeled"
    MIXED = "mixed"


def derive_usable_output(
    *,
    run_status: RunStatus | str,
    segments_scored: int,
) -> bool:
    """True only when complete with at least one successfully scored segment."""
    status = run_status.value if isinstance(run_status, RunStatus) else str(run_status)
    return status == RunStatus.COMPLETE.value and int(segments_scored) > 0


def derive_run_status_from_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    eligible_failed: int = 0,
) -> tuple[RunStatus, int, int]:
    """
    Derive run_status from per-row evaluation states.

    Complete means every eligible non-empty segment received a valid scored
    vector (no failed rows among eligible). Any eligible failure → partial
    (if any scored) or failed (if none scored).

    Returns (run_status, segments_scored, segments_failed).
    """
    scored = 0
    failed = int(eligible_failed)
    for row in rows:
        state = str(row.get("evaluation_state") or "")
        if state == EvaluationState.SCORED.value:
            scored += 1
        elif state == EvaluationState.FAILED.value:
            failed += 1
    if failed > 0:
        if scored > 0:
            return RunStatus.PARTIAL, scored, failed
        return RunStatus.FAILED, scored, failed
    return RunStatus.COMPLETE, scored, failed
