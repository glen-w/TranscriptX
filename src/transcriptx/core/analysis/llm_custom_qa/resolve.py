"""Effective questions resolver — sole post-resolve runtime authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Optional

from transcriptx.core.analysis.llm_custom_qa.constants import MAX_ANSWER_CHARS
from transcriptx.core.analysis.llm_custom_qa.question_identity import (
    CanonicalQuestion,
    canonicalize_questions,
    project_question_texts,
)
from transcriptx.core.analysis.llm_custom_qa.request_questions import (
    structured_library_from_settings,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_canonical_json

ResolvedFrom = Literal["library", "request", "explicit_empty"]


@dataclass(frozen=True)
class EffectiveCustomQAQuestions:
    """Immutable questions authority for one analysis run (v1 analyser view)."""

    questions: tuple[str, ...]
    questions_hash: str
    empty: bool
    resolved_from: ResolvedFrom
    max_questions_per_run: int
    max_question_chars: int
    max_run_total_question_chars: int
    max_answer_chars: int
    # Structured canonical questions retained for scopes (v2 / bridge).
    structured: tuple[CanonicalQuestion, ...] = ()
    question_order: tuple[str, ...] = ()

    def to_metadata(self) -> dict[str, Any]:
        return {
            "questions_requested": list(self.questions),
            "questions_hash": self.questions_hash,
            "resolved_from": self.resolved_from,
            "question_order": list(self.question_order),
            "structured": [
                {
                    "text": q.text,
                    "scopes": q.scopes.as_dict(),
                    "question_id": q.question_id,
                }
                for q in self.structured
            ],
        }


def questions_hash_for(questions: tuple[str, ...] | list[str]) -> str:
    return sha256_canonical_json(list(questions))


def _limits_from_settings(settings: Any) -> dict[str, int]:
    return {
        "max_questions_per_run": int(getattr(settings, "max_questions_per_run", 8)),
        "max_question_chars": int(getattr(settings, "max_question_chars", 500)),
        "max_run_total_question_chars": int(
            getattr(settings, "max_run_total_question_chars", 4000)
        ),
        "max_answer_chars": int(
            getattr(settings, "max_answer_chars", MAX_ANSWER_CHARS)
        ),
        "max_library_questions": int(getattr(settings, "max_library_questions", 50)),
        "max_library_total_question_chars": int(
            getattr(settings, "max_library_total_question_chars", 20000)
        ),
    }


def _build_effective(
    *,
    structured_raw: Any,
    resolved_from: ResolvedFrom,
    limits: dict[str, int],
) -> EffectiveCustomQAQuestions:
    if structured_raw is None or (
        isinstance(structured_raw, (list, tuple)) and len(structured_raw) == 0
    ):
        return EffectiveCustomQAQuestions(
            questions=(),
            questions_hash=questions_hash_for(()),
            empty=True,
            resolved_from=resolved_from,
            max_questions_per_run=limits["max_questions_per_run"],
            max_question_chars=limits["max_question_chars"],
            max_run_total_question_chars=limits["max_run_total_question_chars"],
            max_answer_chars=limits["max_answer_chars"],
            structured=(),
            question_order=(),
        )

    # Accept list[str] or structured question dicts
    canonical, order = canonicalize_questions(
        structured_raw,
        max_questions=limits["max_questions_per_run"],
        max_question_chars=limits["max_question_chars"],
        max_total_question_chars=limits["max_run_total_question_chars"],
    )
    v1_texts = project_question_texts(canonical)
    # Text-list hash for the live writer path
    return EffectiveCustomQAQuestions(
        questions=v1_texts,
        questions_hash=questions_hash_for(v1_texts),
        empty=len(v1_texts) == 0,
        resolved_from=resolved_from,
        max_questions_per_run=limits["max_questions_per_run"],
        max_question_chars=limits["max_question_chars"],
        max_run_total_question_chars=limits["max_run_total_question_chars"],
        max_answer_chars=limits["max_answer_chars"],
        structured=canonical,
        question_order=order,
    )


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

    if not request_field_present or request_questions is None:
        resolved_from: ResolvedFrom = "library"
        raw = structured_library_from_settings(settings)
        return _build_effective(
            structured_raw=raw, resolved_from=resolved_from, limits=limits
        )
    if isinstance(request_questions, (list, tuple)) and len(request_questions) == 0:
        return _build_effective(
            structured_raw=[], resolved_from="explicit_empty", limits=limits
        )
    return _build_effective(
        structured_raw=request_questions, resolved_from="request", limits=limits
    )


def normalize_library_questions(
    raw: Any,
    *,
    settings: Any = None,
) -> tuple[dict[str, Any], ...]:
    """Normalise questions for library save → structured dicts."""
    if settings is None:
        from transcriptx.core.utils.config import get_config

        settings = get_config().analysis.llm_custom_qa
    limits = _limits_from_settings(settings)
    # Accept list[str] input as well as structured question dicts
    canonical, _ = canonicalize_questions(
        raw,
        max_questions=limits["max_library_questions"],
        max_question_chars=limits["max_question_chars"],
        max_total_question_chars=limits["max_library_total_question_chars"],
    )
    return tuple({"text": q.text, "scopes": q.scopes.as_dict()} for q in canonical)


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
