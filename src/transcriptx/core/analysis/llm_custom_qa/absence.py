"""Absence detector: when input truncated, prefer not_in_provided_excerpt abstain."""

from __future__ import annotations

from typing import Any

from transcriptx.core.analysis.llm_custom_qa.constants import ABSENCE_DETECTOR_VERSION


def apply_absence_detector(
    answers: list[dict[str, Any]],
    *,
    truncated: bool,
    diagnostics: dict[str, int],
) -> list[dict[str, Any]]:
    """Only when truncated: leave model abstain `not_in_provided_excerpt` as-is.

    Additionally, answered rows that failed grounding stay unavailable.
    Versioned hook for future lexical absence checks.
    """
    del ABSENCE_DETECTOR_VERSION  # reserved for cache identity / future logic
    if not truncated:
        return answers
    out: list[dict[str, Any]] = []
    for row in answers:
        if (
            row.get("status") == "abstained"
            and row.get("abstain_reason") == "not_in_provided_excerpt"
        ):
            diagnostics["absence_detector_hits"] = (
                int(diagnostics.get("absence_detector_hits", 0)) + 1
            )
            diagnostics["input_truncated_overrides"] = int(
                diagnostics.get("input_truncated_overrides", 0)
            )
        out.append(row)
    return out
