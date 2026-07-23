"""Effective questions resolver — sole post-resolve runtime authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional

from transcriptx.core.analysis.llm_custom_qa.constants import MAX_ANSWER_CHARS
from transcriptx.core.analysis.llm_custom_qa.normalize import normalize_questions
from transcriptx.core.analysis.llm_support.hashing import sha256_canonical_json

ResolvedFrom = Literal["library", "request", "explicit_empty"]


@dataclass(frozen=True)
class EffectiveCustomQAQuestions:
    """Immutable questions authority for one analysis run."""

    questions: tuple[str, ...]
    questions_hash: str
    empty: bool
    resolved_from: ResolvedFrom
    max_questions_per_run: int
    max_question_chars: int
    max_run_total_question_chars: int
    max_answer_chars: int

    def to_metadata(self) -> dict[str, Any]:
        return {
            "questions_requested": list(self.questions),
            "questions_hash": self.questions_hash,
            "resolved_from": self.resolved_from,
        }


def questions_hash_for(questions: tuple[str, ...] | list[str]) -> str:
    return sha256_canonical_json(list(questions))


def _limits_from_settings(settings: Any) -> dict[str, int]:
    return {
        "max_questions_per_run": int(
            getattr(settings, "max_questions_per_run", 8)
        ),
        "max_question_chars": int(getattr(settings, "max_question_chars", 500)),
        "max_run_total_question_chars": int(
            getattr(settings, "max_run_total_question_chars", 4000)
        ),
        "max_answer_chars": int(
            getattr(settings, "max_answer_chars", MAX_ANSWER_CHARS)
        ),
        "max_library_questions": int(
            getattr(settings, "max_library_questions", 50)
        ),
        "max_library_total_question_chars": int(
            getattr(settings, "max_library_total_question_chars", 20000)
        ),
    }


def resolve_effective_custom_qa_questions(
    *,
    request_questions: Any = None,
    request_field_present: bool = False,
    settings: Any = None,
) -> EffectiveCustomQAQuestions:
    """Resolve effective questions.

    Request field semantics:
    - Omitted or explicit ``null`` → ``library`` (normalised saved_questions)
    - Explicit ``[]`` → ``explicit_empty``
    - Non-empty list → ``request``

    Success always returns a valid immutable object (including empty).
    Failure raises ``CustomQAQuestionsValidationError``.
    """
    if settings is None:
        from transcriptx.core.utils.config import get_config

        settings = get_config().analysis.llm_custom_qa
    limits = _limits_from_settings(settings)

    # Distinguish omit/null from explicit []
    if not request_field_present or request_questions is None:
        resolved_from: ResolvedFrom = "library"
        raw = getattr(settings, "saved_questions", []) or []
        questions = normalize_questions(
            raw,
            max_questions=limits["max_questions_per_run"],
            max_question_chars=limits["max_question_chars"],
            max_total_question_chars=limits["max_run_total_question_chars"],
        )
    elif isinstance(request_questions, (list, tuple)) and len(request_questions) == 0:
        resolved_from = "explicit_empty"
        questions = ()
    else:
        resolved_from = "request"
        questions = normalize_questions(
            request_questions,
            max_questions=limits["max_questions_per_run"],
            max_question_chars=limits["max_question_chars"],
            max_total_question_chars=limits["max_run_total_question_chars"],
        )

    qhash = questions_hash_for(questions)
    return EffectiveCustomQAQuestions(
        questions=questions,
        questions_hash=qhash,
        empty=len(questions) == 0,
        resolved_from=resolved_from,
        max_questions_per_run=limits["max_questions_per_run"],
        max_question_chars=limits["max_question_chars"],
        max_run_total_question_chars=limits["max_run_total_question_chars"],
        max_answer_chars=limits["max_answer_chars"],
    )


def normalize_library_questions(
    raw: Any,
    *,
    settings: Any = None,
) -> tuple[str, ...]:
    """Normalise questions for library save (library totals + max_question_chars)."""
    if settings is None:
        from transcriptx.core.utils.config import get_config

        settings = get_config().analysis.llm_custom_qa
    limits = _limits_from_settings(settings)
    return normalize_questions(
        raw,
        max_questions=limits["max_library_questions"],
        max_question_chars=limits["max_question_chars"],
        max_total_question_chars=limits["max_library_total_question_chars"],
    )


def resolve_from_mapping(
    payload: Optional[Mapping[str, Any]],
    *,
    settings: Any = None,
    field_name: str = "llm_custom_qa_questions",
) -> EffectiveCustomQAQuestions:
    """Resolve from a request-like mapping that may omit the field."""
    if payload is None:
        return resolve_effective_custom_qa_questions(
            request_questions=None,
            request_field_present=False,
            settings=settings,
        )
    present = field_name in payload
    value = payload.get(field_name) if present else None
    return resolve_effective_custom_qa_questions(
        request_questions=value,
        request_field_present=present,
        settings=settings,
    )
