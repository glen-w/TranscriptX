"""Custom questions LLM analysis module (`llm_custom_qa`)."""

from __future__ import annotations

from transcriptx.core.analysis.llm_custom_qa.analyze import LLMCustomQAAnalysis
from transcriptx.core.analysis.llm_custom_qa.gating import consumer_requires_live_llm
from transcriptx.core.analysis.llm_custom_qa.questions_binding import (
    bind_custom_qa_questions,
    get_bound_custom_qa_questions,
    reset_custom_qa_questions,
)
from transcriptx.core.analysis.llm_custom_qa.resolve import (
    EffectiveCustomQAQuestions,
    normalize_library_questions,
    resolve_effective_custom_qa_questions,
)

__all__ = [
    "LLMCustomQAAnalysis",
    "EffectiveCustomQAQuestions",
    "bind_custom_qa_questions",
    "get_bound_custom_qa_questions",
    "reset_custom_qa_questions",
    "resolve_effective_custom_qa_questions",
    "normalize_library_questions",
    "consumer_requires_live_llm",
]
