from __future__ import annotations

from hashlib import sha1
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator


def _stable_sha1(value: str) -> str:
    return sha1(value.encode("utf-8")).hexdigest()


class CorrectionConditions(BaseModel):
    speaker: Optional[str] = None
    min_token_len: Optional[int] = None
    context_any: Optional[List[str]] = None
    case_sensitive: bool = False
    word_boundary: bool = True


class CorrectionRule(BaseModel):
    id: Optional[str] = None
    type: Literal["token", "phrase", "acronym", "regex"]
    wrong: List[str]
    right: str
    scope: Literal["global", "project", "transcript"]
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    auto_apply: bool = False
    conditions: Optional[CorrectionConditions] = None
    is_person_name: bool = False  # when True, skip applying to unidentified speakers

    @staticmethod
    def compute_id(
        rule_type: str, wrong: List[str], right: str, scope: str = ""
    ) -> str:
        # scope excluded so id is stable across layers (global vs project)
        signature = f"{rule_type}:{sorted(wrong)}:{right}"
        return _stable_sha1(signature)

    @model_validator(mode="after")
    def ensure_id(self) -> "CorrectionRule":
        if not self.id:
            self.id = self.compute_id(self.type, self.wrong, self.right, self.scope)
        return self


class Occurrence(BaseModel):
    occurrence_id: Optional[str] = None
    segment_id: str
    speaker: Optional[str] = None
    time_start: Optional[float] = None
    time_end: Optional[float] = None
    span: Optional[Tuple[int, int]] = None
    snippet: str

    @field_validator("span", mode="before")
    def normalize_span(cls, value: Any) -> Optional[Tuple[int, int]]:
        if value is None:
            return None
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return (int(value[0]), int(value[1]))
        raise ValueError("span must be a 2-item list/tuple")

    @model_validator(mode="after")
    def ensure_occurrence_id(self) -> "Occurrence":
        if not self.occurrence_id:
            span_value = f"{self.span[0]}:{self.span[1]}" if self.span else "no-span"
            signature = f"{self.segment_id}:{span_value}:{self.snippet}"
            self.occurrence_id = _stable_sha1(signature)
        return self


class Candidate(BaseModel):
    candidate_id: Optional[str] = None
    rule_id: Optional[str] = None
    proposed_wrong: str
    proposed_right: str
    kind: Literal["memory_hit", "acronym", "consistency", "fuzzy", "ner_variant"]
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    occurrences: List[Occurrence] = Field(default_factory=list)

    @staticmethod
    def compute_id(kind: str, proposed_wrong: str, proposed_right: str) -> str:
        signature = f"{kind}:{proposed_wrong}:{proposed_right}"
        return _stable_sha1(signature)

    @model_validator(mode="after")
    def ensure_candidate_id(self) -> "Candidate":
        if not self.candidate_id:
            self.candidate_id = self.compute_id(
                self.kind, self.proposed_wrong, self.proposed_right
            )
        return self


class Decision(BaseModel):
    candidate_id: str
    decision: Literal["apply_all", "apply_some", "reject", "skip", "learn"]
    selected_occurrence_ids: Optional[List[str]] = None
    new_rule: Optional[CorrectionRule] = None
    notes: Optional[str] = None


class CorrectionMemory(BaseModel):
    rules: Dict[str, CorrectionRule] = Field(default_factory=dict)

    def merge(self, other: "CorrectionMemory") -> "CorrectionMemory":
        merged = dict(self.rules)
        merged.update(other.rules)
        return CorrectionMemory(rules=merged)
