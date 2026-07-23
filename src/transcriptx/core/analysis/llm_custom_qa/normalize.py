"""Question normalisation for llm_custom_qa."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Sequence

from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAQuestionsValidationError,
)

_ALLOWED_PRE_COLLAPSE_CONTROLS = frozenset({"\n", "\t"})
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _reject_scalar_sequence(raw: Any) -> None:
    """Reject str/bytes (and non-sequences) before iterating."""
    if isinstance(raw, (str, bytes, bytearray)):
        raise CustomQAQuestionsValidationError(
            "Questions must be a sequence of strings, not a scalar string/bytes",
            error_context={"type": type(raw).__name__},
        )
    if not isinstance(raw, Sequence):
        raise CustomQAQuestionsValidationError(
            "Questions must be a sequence of strings",
            error_context={"type": type(raw).__name__},
        )


def _normalize_one(value: Any, *, index: int, max_question_chars: int) -> str | None:
    if not isinstance(value, str) or isinstance(value, bool):
        # bool is a subclass of int, not str — keep explicit for clarity
        raise CustomQAQuestionsValidationError(
            f"Question at index {index} must be a strict str (no coercion)",
            error_context={"index": index, "type": type(value).__name__},
        )
    text = unicodedata.normalize("NFC", value)
    for ch in text:
        if unicodedata.category(ch).startswith("C") and ch not in _ALLOWED_PRE_COLLAPSE_CONTROLS:
            if _CONTROL_RE.search(ch) or ch not in _ALLOWED_PRE_COLLAPSE_CONTROLS:
                # Disallow control chars other than \n/\t before collapse
                if ch not in ("\n", "\t"):
                    raise CustomQAQuestionsValidationError(
                        f"Question at index {index} contains disallowed control characters",
                        error_context={"index": index},
                    )
    # Collapse whitespace/newlines to single ASCII spaces; trim
    collapsed = " ".join(text.split())
    if not collapsed:
        return None
    if len(collapsed) > max_question_chars:
        raise CustomQAQuestionsValidationError(
            f"Question at index {index} exceeds max_question_chars={max_question_chars}",
            error_context={
                "index": index,
                "length": len(collapsed),
                "max_question_chars": max_question_chars,
            },
        )
    return collapsed


def normalize_questions(
    raw: Any,
    *,
    max_questions: int,
    max_question_chars: int,
    max_total_question_chars: int,
) -> tuple[str, ...]:
    """Normalise a question list; raise on oversize (never silent truncate)."""
    _reject_scalar_sequence(raw)
    normalised: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(raw):
        if not isinstance(value, str):
            raise CustomQAQuestionsValidationError(
                f"Question at index {index} must be a strict str (no coercion)",
                error_context={"index": index, "type": type(value).__name__},
            )
        item = _normalize_one(
            value, index=index, max_question_chars=max_question_chars
        )
        if item is None:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalised.append(item)

    if len(normalised) > max_questions:
        raise CustomQAQuestionsValidationError(
            f"Too many questions: {len(normalised)} > max_questions={max_questions}",
            error_context={
                "count": len(normalised),
                "max_questions": max_questions,
            },
        )
    total_chars = sum(len(q) for q in normalised)
    if total_chars > max_total_question_chars:
        raise CustomQAQuestionsValidationError(
            f"Total question characters {total_chars} exceeds "
            f"max_total_question_chars={max_total_question_chars}",
            error_context={
                "total_chars": total_chars,
                "max_total_question_chars": max_total_question_chars,
            },
        )
    return tuple(normalised)
