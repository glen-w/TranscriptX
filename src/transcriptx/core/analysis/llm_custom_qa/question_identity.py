"""Canonical question text identity for llm_custom_qa (Stage 0 freeze)."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAQuestionsValidationError,
)
from transcriptx.core.analysis.llm_support.hashing import sha256_canonical_json

_WHITESPACE_RE = re.compile(r"\s+", flags=re.UNICODE)


@dataclass(frozen=True)
class QuestionScopes:
    global_scope: bool
    per_speaker: bool

    def as_dict(self) -> dict[str, bool]:
        return {"global": self.global_scope, "per_speaker": self.per_speaker}

    def union(self, other: "QuestionScopes") -> "QuestionScopes":
        return QuestionScopes(
            global_scope=self.global_scope or other.global_scope,
            per_speaker=self.per_speaker or other.per_speaker,
        )


@dataclass(frozen=True)
class CanonicalQuestion:
    question_id: str
    text: str
    scopes: QuestionScopes


def normalize_question_text(raw: Any, *, max_question_chars: int) -> str:
    """Exact Stage 0 text-normalisation algorithm."""
    if not isinstance(raw, str):
        raise CustomQAQuestionsValidationError(
            "Question text must be a string",
            error_context={"reason": "type", "got": type(raw).__name__},
        )
    text = unicodedata.normalize("NFC", raw)
    text = text.strip()
    text = _WHITESPACE_RE.sub(" ", text)
    if not text:
        raise CustomQAQuestionsValidationError(
            "Question text must be non-empty after normalisation",
            error_context={"reason": "empty"},
        )
    if len(text) > max_question_chars:
        raise CustomQAQuestionsValidationError(
            f"Question exceeds max_question_chars ({max_question_chars})",
            error_context={"reason": "max_chars", "length": len(text)},
        )
    return text


def question_id_for_text(normalised_text: str) -> str:
    """Fixed 32-hex content-derived id: q_ + first 16 bytes of SHA-256."""
    digest = hashlib.sha256(normalised_text.encode("utf-8")).hexdigest()[:32]
    return f"q_{digest}"


def _scopes_from_mapping(raw: Mapping[str, Any]) -> QuestionScopes:
    scopes_raw = raw.get("scopes")
    if not isinstance(scopes_raw, Mapping):
        raise CustomQAQuestionsValidationError(
            "Question scopes must be an object",
            error_context={"reason": "scopes_type"},
        )
    # Reject unknown keys at scopes level
    allowed = {"global", "per_speaker"}
    extra = set(scopes_raw.keys()) - allowed
    if extra:
        raise CustomQAQuestionsValidationError(
            f"Unknown scope keys: {sorted(extra)}",
            error_context={"reason": "scopes_extra"},
        )
    global_scope = bool(scopes_raw.get("global", False))
    per_speaker = bool(scopes_raw.get("per_speaker", False))
    if not global_scope and not per_speaker:
        raise CustomQAQuestionsValidationError(
            "At least one scope must be true",
            error_context={"reason": "no_scope"},
        )
    return QuestionScopes(global_scope=global_scope, per_speaker=per_speaker)


def legacy_string_to_structured(text: str) -> dict[str, Any]:
    """Explicit legacy migration defaults (not model Field defaults)."""
    return {
        "text": text,
        "scopes": {"global": True, "per_speaker": False},
    }


def canonicalize_questions(
    raw: Any,
    *,
    max_questions: int,
    max_question_chars: int,
    max_total_question_chars: int,
) -> tuple[tuple[CanonicalQuestion, ...], tuple[str, ...]]:
    """
    Normalize, merge duplicates (scope union), assign content ids.

    Returns (canonical_questions_in_display_order, question_order ids).
    ``questions_hash`` must be computed via ``questions_hash_for_canonical``.
    """
    if raw is None:
        raw = []
    if not isinstance(raw, (list, tuple)):
        raise CustomQAQuestionsValidationError(
            "Questions must be a list",
            error_context={"reason": "type"},
        )

    # Reject mixed str/object lists.
    kinds = set()
    for item in raw:
        if isinstance(item, str):
            kinds.add("str")
        elif isinstance(item, Mapping):
            kinds.add("obj")
        else:
            raise CustomQAQuestionsValidationError(
                "Question entries must be strings or objects",
                error_context={"reason": "entry_type"},
            )
    if len(kinds) > 1:
        raise CustomQAQuestionsValidationError(
            "Mixed string/object question lists are rejected",
            error_context={"reason": "mixed_list"},
        )

    # Merge by normalised text; preserve first-seen order.
    merged: dict[str, CanonicalQuestion] = {}
    order: list[str] = []
    total_chars = 0

    for item in raw:
        if isinstance(item, str):
            item = legacy_string_to_structured(item)
        elif isinstance(item, Mapping):
            # Forbid unknown top-level keys beyond text/scopes
            allowed = {"text", "scopes"}
            extra = set(item.keys()) - allowed
            if extra:
                raise CustomQAQuestionsValidationError(
                    f"Unknown question keys: {sorted(extra)}",
                    error_context={"reason": "extra_keys"},
                )
            if "text" not in item:
                raise CustomQAQuestionsValidationError(
                    "Question object requires text",
                    error_context={"reason": "missing_text"},
                )
        else:
            raise CustomQAQuestionsValidationError(
                "Invalid question entry",
                error_context={"reason": "entry_type"},
            )

        text = normalize_question_text(item["text"], max_question_chars=max_question_chars)
        if "scopes" not in item:
            raise CustomQAQuestionsValidationError(
                "Question object requires scopes",
                error_context={"reason": "missing_scopes"},
            )
        scopes = _scopes_from_mapping(item)

        qid = question_id_for_text(text)
        existing = merged.get(text)
        if existing is None:
            total_chars += len(text)
            if len(merged) >= max_questions:
                raise CustomQAQuestionsValidationError(
                    f"Too many questions (max {max_questions})",
                    error_context={"reason": "max_questions"},
                )
            if total_chars > max_total_question_chars:
                raise CustomQAQuestionsValidationError(
                    "Total question characters exceed limit",
                    error_context={"reason": "max_total_chars"},
                )
            cq = CanonicalQuestion(question_id=qid, text=text, scopes=scopes)
            merged[text] = cq
            order.append(text)
        else:
            merged[text] = CanonicalQuestion(
                question_id=existing.question_id,
                text=existing.text,
                scopes=existing.scopes.union(scopes),
            )

    questions = tuple(merged[t] for t in order)
    question_order = tuple(q.question_id for q in questions)
    return questions, question_order


def questions_hash_for_canonical(questions: Sequence[CanonicalQuestion]) -> str:
    """Hash sorted by question_id, not display order."""
    payload = [
        {
            "question_id": q.question_id,
            "text": q.text,
            "scopes": q.scopes.as_dict(),
        }
        for q in sorted(questions, key=lambda x: x.question_id)
    ]
    return sha256_canonical_json(payload)


def project_questions_for_v1_runtime(
    questions: Sequence[CanonicalQuestion] | Sequence[str],
) -> tuple[str, ...]:
    """Project structured questions to v1 text list immediately before v1 analyser."""
    out: list[str] = []
    for q in questions:
        if isinstance(q, CanonicalQuestion):
            out.append(q.text)
        else:
            out.append(str(q))
    return tuple(out)


def upsert_library_question(
    library: Iterable[Mapping[str, Any] | str],
    *,
    text: str,
    scopes: Mapping[str, bool],
    max_question_chars: int,
    max_library_questions: int,
    max_library_total_question_chars: int,
) -> list[dict[str, Any]]:
    """Atomic upsert by canonical text with scope union."""
    questions, _order = canonicalize_questions(
        list(library) + [{"text": text, "scopes": dict(scopes)}],
        max_questions=max_library_questions,
        max_question_chars=max_question_chars,
        max_total_question_chars=max_library_total_question_chars,
    )
    return [
        {"text": q.text, "scopes": q.scopes.as_dict()} for q in questions
    ]


def merge_evidence_pack_ids(
    a: Optional[list[str]],
    b: Optional[list[str]],
) -> Optional[list[str]]:
    """Settings-level evidence_pack_ids merge rules."""
    if a is None or b is None:
        return None
    if a == [] and b == []:
        return []
    if a == []:
        return sorted(set(b))
    if b == []:
        return sorted(set(a))
    return sorted(set(a) | set(b))
