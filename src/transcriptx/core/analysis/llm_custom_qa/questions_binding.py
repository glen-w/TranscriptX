"""ContextVar binding for structured custom QA questions (branch-neutral)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Optional

from transcriptx.core.analysis.llm_custom_qa.question_identity import CanonicalQuestion
from transcriptx.core.analysis.llm_custom_qa.resolve import (
    EffectiveCustomQAQuestions,
    ResolvedFrom,
)


@dataclass(frozen=True)
class BoundCustomQAQuestions:
    """Branch-neutral immutable binding carried across workers."""

    structured: tuple[CanonicalQuestion, ...]
    question_order: tuple[str, ...]
    resolved_from: ResolvedFrom
    empty: bool
    # v1 projection retained for the live v1 analyser edge only
    v1_effective: Optional[EffectiveCustomQAQuestions] = None


_bound_questions: ContextVar[Optional[BoundCustomQAQuestions]] = ContextVar(
    "llm_custom_qa_bound_questions",
    default=None,
)


def get_bound_custom_qa_questions() -> Optional[EffectiveCustomQAQuestions]:
    """Return v1 EffectiveCustomQAQuestions when bound (compat for analyze.py)."""
    bound = _bound_questions.get()
    if bound is None:
        return None
    return bound.v1_effective


def get_bound_structured_questions() -> Optional[BoundCustomQAQuestions]:
    return _bound_questions.get()


def bind_custom_qa_questions(
    effective: EffectiveCustomQAQuestions | BoundCustomQAQuestions,
) -> Token:
    if isinstance(effective, BoundCustomQAQuestions):
        return _bound_questions.set(effective)
    bound = BoundCustomQAQuestions(
        structured=effective.structured,
        question_order=effective.question_order,
        resolved_from=effective.resolved_from,
        empty=effective.empty,
        v1_effective=effective,
    )
    return _bound_questions.set(bound)


def reset_custom_qa_questions(token: Token) -> None:
    _bound_questions.reset(token)


def copy_bound_questions_to_context() -> Optional[BoundCustomQAQuestions]:
    """Snapshot for worker re-bind (ContextVar may not cross threads)."""
    return _bound_questions.get()
