"""User-facing guidance for llm_action_items failures and truncated output.

Kept separate from the parse/finalize contract so UI, availability checks, and
raise sites share one remediation story without circular imports.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

__all__ = [
    "ACTION_ITEMS_RETRY_GUIDANCE",
    "ACTION_ITEMS_TRUNCATED_WARNING",
    "empty_extracts_user_warning",
    "format_invalid_json_error",
    "format_oversized_output_error",
    "format_module_failure_for_user",
    "is_likely_truncated_json_failure",
    "truncated_output_user_warning",
]


ACTION_ITEMS_RETRY_GUIDANCE = (
    "Re-running with the same settings will usually fail the same way. "
    "Before retrying: set analysis.llm_action_items.effort to max "
    "(Settings → Analysis, or config), prefer a mid/strong JSON-capable model "
    "for llm_action_items — avoid tiny/small tags such as llama3.2:3b "
    "(Settings → LLM model selection), then re-run only the llm_action_items "
    "module."
)

ACTION_ITEMS_TRUNCATED_WARNING = (
    "Meeting extracts may be incomplete: the model response was truncated "
    "before the JSON finished. " + ACTION_ITEMS_RETRY_GUIDANCE
)


def is_likely_truncated_json_failure(message: str | None) -> bool:
    """Heuristic for output-budget truncation / mid-string cuts."""
    text = (message or "").lower()
    needles = (
        "unterminated string",
        "not valid json",
        "truncated",
        "exceeds expected length",
    )
    return any(needle in text for needle in needles)


def format_invalid_json_error(exc: BaseException) -> str:
    detail = str(exc).strip() or type(exc).__name__
    likely = is_likely_truncated_json_failure(detail)
    lead = (
        f"Action items output is not valid JSON (likely truncated mid-response): {detail}"
        if likely
        else f"Action items output is not valid JSON: {detail}"
    )
    return f"{lead}. {ACTION_ITEMS_RETRY_GUIDANCE}"


def format_oversized_output_error(*, length: int, char_limit: int) -> str:
    return (
        f"Action items output exceeds expected length ({length} > {char_limit}). "
        "The model likely ignored the output-token budget. "
        f"{ACTION_ITEMS_RETRY_GUIDANCE}"
    )


def format_module_failure_for_user(
    *,
    module_id: str,
    error_message: str | None,
    error_code: str | None = None,
) -> str:
    """Availability / empty-state copy when artifacts are missing after a failure."""
    detail = (error_message or "").strip()
    code = (error_code or "").strip()
    if module_id == "llm_action_items":
        if detail and is_likely_truncated_json_failure(detail):
            # Avoid duplicating guidance if the stored message already has it.
            if "same settings will usually fail" in detail.lower():
                return (
                    f"`{module_id}` failed for this run (truncated/invalid JSON). "
                    f"{detail}"
                )
            return (
                f"`{module_id}` failed for this run (truncated/invalid JSON). "
                f"{detail} {ACTION_ITEMS_RETRY_GUIDANCE}"
            )
        prefix = f"`{module_id}` failed for this run"
        if code:
            prefix = f"{prefix} [{code}]"
        if detail:
            if "same settings will usually fail" in detail.lower():
                return f"{prefix}: {detail}"
            return f"{prefix}: {detail} {ACTION_ITEMS_RETRY_GUIDANCE}"
        return f"{prefix}. {ACTION_ITEMS_RETRY_GUIDANCE}"

    prefix = f"`{module_id}` failed for this run"
    if code:
        prefix = f"{prefix} [{code}]"
    if detail:
        return f"{prefix}: {detail}"
    return (
        f"{prefix}. Inspect run status / Technical details, fix the underlying "
        "issue, then re-run that module — re-running unchanged usually repeats "
        "the same failure."
    )


def truncated_output_user_warning(
    diagnostics: Optional[Mapping[str, Any]] = None,
) -> str | None:
    """Return a warning when diagnostics mark salvaged/truncated LLM output."""
    if not isinstance(diagnostics, Mapping):
        return None
    if int(diagnostics.get("output_truncated") or 0) <= 0:
        return None
    return ACTION_ITEMS_TRUNCATED_WARNING


def empty_extracts_user_warning(
    diagnostics: Optional[Mapping[str, Any]] = None,
) -> str | None:
    """Explain empty published extracts when the model returned records that were dropped.

    Genuine empty model output (``items_raw == 0``) returns ``None`` so the UI
    can keep the short "No meeting extracts found" caption.
    """
    if not isinstance(diagnostics, Mapping):
        return None
    if int(diagnostics.get("items_committed") or 0) > 0:
        return None
    items_raw = int(diagnostics.get("items_raw") or 0)
    if items_raw <= 0:
        return None

    invalid = int(diagnostics.get("items_invalid_dropped") or 0)
    status_dropped = int(diagnostics.get("status_unsupported_dropped") or 0)
    ungrounded = int(diagnostics.get("items_ungrounded_dropped") or 0)

    reasons: list[str] = []
    if invalid:
        reasons.append(
            f"{invalid} failed schema validation after coercion "
            "(empty text, unusable confidence, or unknown record_type)"
        )
    if status_dropped:
        reasons.append(
            f"{status_dropped} had unsupported status "
            "(or done without required evidence)"
        )
    if ungrounded:
        reasons.append(f"{ungrounded} could not be grounded in the transcript")
    if not reasons:
        reasons.append("none survived filtering")

    detail = "; ".join(reasons)
    schema_heavy = invalid > 0 and status_dropped == 0 and ungrounded == 0
    guidance = (
        "Re-running with the same settings will usually fail the same way. "
        "Prefer a mid/strong JSON-capable model for llm_action_items "
        "(Settings → LLM model selection), then re-run only that module."
        if schema_heavy
        else ACTION_ITEMS_RETRY_GUIDANCE
    )
    return (
        f"No meeting extracts were published: the model returned {items_raw} "
        f"raw record(s), but {detail}. "
        f"{guidance}"
    )
