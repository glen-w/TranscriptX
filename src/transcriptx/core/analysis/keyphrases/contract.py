"""Authoritative keyphrases payload contract (B16)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_ID = "transcriptx.keyphrases.v1"
SEMANTICS_VERSION = "keyphrases_v1"

MethodName = Literal["noun_chunks", "yake", "keybert"]
EvaluationState = Literal["scored", "empty", "skipped", "failed"]
ScoreDirection = Literal["higher_is_better", "lower_is_better"]

SkipReasonCode = Literal[
    "missing_package",
    "model_unavailable",
    "inference_failure",
    "empty_result",
    "unsupported_language",
    "disabled_by_config",
    "oom_or_device_fallback_exhausted",
]

CSV_COLUMNS: tuple[str, ...] = (
    "scope",
    "speaker",
    "method",
    "rank",
    "phrase",
    "canonical_key",
    "token_count",
    "raw_score",
    "score_direction",
    "rank_weight",
    "occurrence_count",
    "segment_support",
)

ALL_METHODS: tuple[MethodName, ...] = ("noun_chunks", "yake", "keybert")


class PhraseEvidence(BaseModel):
    segment_id: str
    speaker_id: str | None = None
    start: float | None = None
    end: float | None = None
    snippet: str | None = None


class RankedPhrase(BaseModel):
    phrase: str
    canonical_key: str
    token_count: int
    rank: int = Field(ge=1)
    raw_score: float
    score_direction: ScoreDirection
    rank_weight: float = Field(ge=0.0, le=1.0)
    occurrence_count: int = Field(ge=0)
    segment_support: int = Field(ge=0)
    evidence: list[PhraseEvidence] = Field(default_factory=list)


class MethodRankBlock(BaseModel):
    method: MethodName
    phrases: list[RankedPhrase] = Field(default_factory=list)
    evaluation_state: EvaluationState


class SkippedMethod(BaseModel):
    method: MethodName
    reason_code: SkipReasonCode
    detail: str | None = None


class KeyphrasesResult(BaseModel):
    schema_id: Literal["transcriptx.keyphrases.v1"] = SCHEMA_ID
    semantics_version: Literal["keyphrases_v1"] = SEMANTICS_VERSION
    usable: bool
    evaluation_state: EvaluationState
    methods_run: list[MethodName] = Field(default_factory=list)
    skipped_methods: list[SkippedMethod] = Field(default_factory=list)
    global_by_method: dict[str, MethodRankBlock] = Field(default_factory=dict)
    speakers_by_method: dict[str, dict[str, MethodRankBlock]] = Field(
        default_factory=dict
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def primary_phrases(self) -> list[RankedPhrase]:
        """Read-only view: noun_chunks global ranks (Insights alias)."""
        block = self.global_by_method.get("noun_chunks")
        if block is None:
            return []
        return list(block.phrases)


def round_score(value: float) -> float:
    return round(float(value), 4)


def empty_result(
    *,
    evaluation_state: EvaluationState,
    usable: bool,
    skipped_methods: list[SkippedMethod] | None = None,
    metadata: dict[str, Any] | None = None,
) -> KeyphrasesResult:
    return KeyphrasesResult(
        usable=usable,
        evaluation_state=evaluation_state,
        methods_run=[],
        skipped_methods=list(skipped_methods or []),
        global_by_method={},
        speakers_by_method={},
        metadata=dict(metadata or {}),
    )
