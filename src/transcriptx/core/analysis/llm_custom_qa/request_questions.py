"""Request-boundary validation for llm_custom_qa_questions."""

from __future__ import annotations

from typing import Any, Optional, Sequence, Union

from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAQuestionsValidationError,
)
from transcriptx.core.analysis.llm_custom_qa.question_identity import (
    CanonicalQuestion,
    canonicalize_questions,
    legacy_string_to_structured,
)

StructuredQuestion = dict[str, Any]
RequestQuestions = Union[list[str], list[StructuredQuestion], None]


def coerce_request_questions(
    raw: Any,
    *,
    field_present: bool,
    max_questions: int,
    max_question_chars: int,
    max_total_question_chars: int,
) -> tuple[Optional[list[StructuredQuestion]], str]:
    """
    Validate request field at the request boundary.

    Returns (structured_or_none, resolved_from_hint) where:
    - field absent/null → (None, \"library\")
    - [] → ([], \"explicit_empty\")
    - list → (structured list, \"request\")
    """
    if not field_present or raw is None:
        return None, "library"
    if not isinstance(raw, (list, tuple)):
        raise CustomQAQuestionsValidationError(
            "llm_custom_qa_questions must be a list or null",
            error_context={"reason": "type"},
        )
    if len(raw) == 0:
        return [], "explicit_empty"

    # One-release: accept list[str] → global-only structured
    kinds: set[str] = set()
    migrated: list[Any] = []
    for item in raw:
        if isinstance(item, str):
            kinds.add("str")
            migrated.append(legacy_string_to_structured(item))
        elif isinstance(item, dict):
            kinds.add("obj")
            migrated.append(item)
        else:
            raise CustomQAQuestionsValidationError(
                "Malformed llm_custom_qa_questions entry",
                error_context={"reason": "entry_type"},
            )
    if len(kinds) > 1:
        raise CustomQAQuestionsValidationError(
            "Mixed string/object llm_custom_qa_questions rejected",
            error_context={"reason": "mixed_list"},
        )

    questions, _order = canonicalize_questions(
        migrated,
        max_questions=max_questions,
        max_question_chars=max_question_chars,
        max_total_question_chars=max_total_question_chars,
    )
    return [
        {"text": q.text, "scopes": q.scopes.as_dict()} for q in questions
    ], "request"


def structured_library_from_settings(settings: Any) -> list[StructuredQuestion]:
    """Export settings.saved_questions as plain dicts (idempotent)."""
    raw = getattr(settings, "saved_questions", []) or []
    out: list[StructuredQuestion] = []
    for item in raw:
        if isinstance(item, str):
            out.append(legacy_string_to_structured(item))
        elif isinstance(item, dict):
            out.append(
                {
                    "text": item["text"],
                    "scopes": dict(item.get("scopes") or {"global": True, "per_speaker": False}),
                }
            )
        else:
            # Pydantic model
            text = getattr(item, "text", None)
            scopes = getattr(item, "scopes", None)
            if text is None:
                continue
            if hasattr(scopes, "global_scope"):
                scopes_dict = {
                    "global": bool(scopes.global_scope),
                    "per_speaker": bool(scopes.per_speaker),
                }
            elif isinstance(scopes, dict):
                scopes_dict = {
                    "global": bool(
                        scopes.get("global", scopes.get("global_scope", False))
                    ),
                    "per_speaker": bool(scopes.get("per_speaker", False)),
                }
            else:
                scopes_dict = {"global": True, "per_speaker": False}
            out.append({"text": str(text), "scopes": scopes_dict})
    return out


def canonical_from_structured(
    structured: Sequence[StructuredQuestion],
    *,
    max_questions: int,
    max_question_chars: int,
    max_total_question_chars: int,
) -> tuple[CanonicalQuestion, ...]:
    qs, _ = canonicalize_questions(
        list(structured),
        max_questions=max_questions,
        max_question_chars=max_question_chars,
        max_total_question_chars=max_total_question_chars,
    )
    return qs
