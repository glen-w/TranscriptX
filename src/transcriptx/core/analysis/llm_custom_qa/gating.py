"""Conditional LLM consumer gate for llm_custom_qa."""

from __future__ import annotations

from typing import Optional

from transcriptx.core.analysis.llm_custom_qa.constants import MODULE_NAME
from transcriptx.core.analysis.llm_custom_qa.questions_binding import (
    get_bound_custom_qa_questions,
)
from transcriptx.core.analysis.llm_custom_qa.resolve import EffectiveCustomQAQuestions


def consumer_requires_live_llm(
    module_name: str,
    effective: Optional[EffectiveCustomQAQuestions] = None,
) -> bool:
    """Return whether this module needs a live LLM for the current effective state.

    ``llm_custom_qa`` + empty questions → False (module still schedules and
    writes the empty-run success artifact without Ollama).
    Other modules keep normal readiness (True when they are LLM modules —
    callers should only use this for conditional overrides).
    """
    if module_name != MODULE_NAME:
        return True
    if effective is None:
        effective = get_bound_custom_qa_questions()
    if effective is not None and effective.empty:
        return False
    return True
