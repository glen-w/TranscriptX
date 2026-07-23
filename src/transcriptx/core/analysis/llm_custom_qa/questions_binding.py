"""ContextVar binding for EffectiveCustomQAQuestions (sole run authority)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Optional

from transcriptx.core.analysis.llm_custom_qa.resolve import EffectiveCustomQAQuestions

_bound_questions: ContextVar[Optional[EffectiveCustomQAQuestions]] = ContextVar(
    "llm_custom_qa_effective_questions",
    default=None,
)


def get_bound_custom_qa_questions() -> Optional[EffectiveCustomQAQuestions]:
    return _bound_questions.get()


def bind_custom_qa_questions(
    effective: EffectiveCustomQAQuestions,
) -> Token:
    return _bound_questions.set(effective)


def reset_custom_qa_questions(token: Token) -> None:
    _bound_questions.reset(token)
