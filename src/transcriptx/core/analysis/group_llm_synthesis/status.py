"""overall_status matrix for committed ACTIVE/COMMIT payloads."""

from __future__ import annotations

from transcriptx.core.analysis.group_llm_synthesis.schemas import (
    OverallStatus,
    UnitStatus,
)


def compute_overall_status(
    *,
    global_status: UnitStatus,
    speaker_ok: int,
    speaker_fail: int,
    speaker_skip: int,
) -> OverallStatus:
    """Map global unit status + speaker counts to ACTIVE/COMMIT overall_status.

    ``cancelled`` is never returned (attempt-only).
    """
    del speaker_skip  # counted for eligibility elsewhere; matrix uses ok/fail
    g = global_status
    ok = int(speaker_ok)
    fail = int(speaker_fail)

    if g == "success" and fail == 0:
        return "success"
    if g == "skipped" and ok >= 1 and fail == 0:
        return "success"
    if g == "skipped" and ok == 0 and fail == 0:
        return "skipped"
    if g == "failed" and ok == 0:
        return "failed"
    if g == "failed" and ok >= 1:
        return "partial"
    if g == "success" and fail >= 1:
        return "partial"
    if g == "skipped" and fail >= 1 and ok >= 1:
        return "partial"
    if g == "skipped" and fail >= 1 and ok == 0:
        return "failed"
    return "failed"
