"""Model response schemas: envelope then per-row validation."""

from __future__ import annotations

import json
import math
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from transcriptx.core.analysis.llm_custom_qa.constants import MAX_QUOTES_FROM_MODEL
from transcriptx.core.analysis.llm_custom_qa.errors import (
    CustomQAModelResponseInvalidError,
)

ModelAbstainReason = Literal[
    "insufficient_evidence",
    "ambiguous",
    "out_of_scope",
    "not_in_provided_excerpt",
]

ModelAnswerStatus = Literal["answered", "abstained"]


def _is_strict_json_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return False


class LLMCustomQAModelQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)


class LLMCustomQAModelAnswerRow(BaseModel):
    """Strict per-row model schema (never fails the module alone)."""

    # Ignore unknown keys — local models often add helper fields.
    model_config = ConfigDict(extra="ignore")

    question_index: int
    status: ModelAnswerStatus
    answer: Optional[str] = None
    # Optional for v1; v2 answer processing requires non-empty reasoning when answered.
    reasoning: Optional[str] = None
    abstain_reason: Optional[ModelAbstainReason] = None
    # Local models (e.g. mistral-nemo) often emit null confidence on abstains.
    confidence: Optional[float] = None
    quotes: list[str] = Field(default_factory=list)

    @field_validator("question_index", mode="before")
    @classmethod
    def _strict_index(cls, value: Any) -> int:
        if not _is_strict_json_int(value):
            raise ValueError("question_index must be a strict JSON integer")
        return int(value)

    @field_validator("confidence", mode="before")
    @classmethod
    def _strict_confidence(cls, value: Any) -> Optional[float]:
        if value is None:
            return None
        if not _is_finite_number(value):
            raise ValueError("confidence must be a finite JSON number (bool rejected)")
        conf = float(value)
        if conf < 0.0 or conf > 1.0:
            raise ValueError("confidence must be in [0, 1]")
        return conf

    @field_validator("quotes", mode="before")
    @classmethod
    def _quotes_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("quotes must be an array")
        if len(value) > MAX_QUOTES_FROM_MODEL:
            raise ValueError(f"quotes exceeds max {MAX_QUOTES_FROM_MODEL}")
        out: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("quote entries must be strings")
            cleaned = " ".join(item.split())
            if not cleaned:
                raise ValueError("quotes must not contain empty normalised strings")
            out.append(cleaned)
        return out

    @model_validator(mode="after")
    def _status_fields(self) -> "LLMCustomQAModelAnswerRow":
        if self.status == "answered":
            if self.answer is None or not str(self.answer).strip():
                raise ValueError("answered rows require a non-empty answer")
            if self.abstain_reason is not None:
                raise ValueError("answered rows must not set abstain_reason")
            # Length vs max_answer_chars enforced in two-pass (answers_over_limit)
        elif self.status == "abstained":
            if self.answer is not None and str(self.answer).strip():
                raise ValueError("abstained rows must not include an answer")
            if self.abstain_reason is None:
                raise ValueError("abstained rows require abstain_reason")
            if self.quotes:
                raise ValueError("abstained rows must not include quotes")
        return self


class LLMCustomQAModelEnvelope(BaseModel):
    """Strict envelope: answers is a raw JSON array of Any."""

    model_config = ConfigDict(extra="forbid")

    answers: list[Any]


def parse_model_envelope(raw: str | bytes | dict[str, Any]) -> list[Any]:
    """Parse top-level model response; raise only on envelope failures."""
    if isinstance(raw, (str, bytes, bytearray)):
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        try:
            loaded = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CustomQAModelResponseInvalidError(
                f"Invalid JSON model response: {exc}",
                error_context={"reason": "invalid_json"},
            ) from exc
    elif isinstance(raw, dict):
        loaded = raw
    else:
        raise CustomQAModelResponseInvalidError(
            "Model response root must be a JSON object",
            error_context={"reason": "non_object_root", "type": type(raw).__name__},
        )

    if not isinstance(loaded, dict):
        raise CustomQAModelResponseInvalidError(
            "Model response root must be a JSON object",
            error_context={"reason": "non_object_root"},
        )
    if "answers" not in loaded:
        raise CustomQAModelResponseInvalidError(
            "Model response missing answers",
            error_context={"reason": "missing_answers"},
        )
    if not isinstance(loaded["answers"], list):
        raise CustomQAModelResponseInvalidError(
            "Model response answers must be an array",
            error_context={"reason": "answers_not_array"},
        )
    try:
        envelope = LLMCustomQAModelEnvelope.model_validate(loaded)
    except Exception as exc:
        raise CustomQAModelResponseInvalidError(
            f"Model response envelope invalid: {exc}",
            error_context={"reason": "envelope_extra_or_invalid"},
        ) from exc
    return list(envelope.answers)


def try_parse_answer_row(raw: Any) -> LLMCustomQAModelAnswerRow | None:
    """Independently validate one row; return None if invalid."""
    try:
        return LLMCustomQAModelAnswerRow.model_validate(raw)
    except Exception:
        return None


def extract_question_index(raw: Any) -> int | None:
    """Return in-range-capable integer question_index if present, else None."""
    if not isinstance(raw, dict):
        return None
    value = raw.get("question_index")
    if not _is_strict_json_int(value):
        return None
    return int(value)
