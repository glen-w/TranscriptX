"""LLM feedback event models and identity helpers."""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

EVENT_SCHEMA_ID = "llm_feedback_event_v1"
NOTE_MAX_CODEPOINTS = 2000
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class FeedbackRating(str, Enum):
    UP = "up"
    DOWN = "down"


class FeedbackReason(str, Enum):
    HELPFUL = "helpful"
    TOO_VAGUE = "too_vague"
    INACCURATE = "inaccurate"
    TOO_LONG = "too_long"
    TOO_SHORT = "too_short"
    WRONG_STYLE = "wrong_style"
    OTHER = "other"


class FeedbackSurface(str, Enum):
    INSIGHTS_BLOCK = "insights_block"
    OVERVIEW_HERO = "overview_hero"
    CUSTOM_QA_ANSWER = "custom_qa_answer"
    CHART_CAPTION = "chart_caption"


class SubjectType(str, Enum):
    TRANSCRIPT = "transcript"
    GROUP = "group"


REASONS_BY_RATING: Mapping[FeedbackRating, frozenset[FeedbackReason]] = {
    FeedbackRating.UP: frozenset({FeedbackReason.HELPFUL, FeedbackReason.OTHER}),
    FeedbackRating.DOWN: frozenset(
        {
            FeedbackReason.TOO_VAGUE,
            FeedbackReason.INACCURATE,
            FeedbackReason.TOO_LONG,
            FeedbackReason.TOO_SHORT,
            FeedbackReason.WRONG_STYLE,
            FeedbackReason.OTHER,
        }
    ),
}

REASON_LABELS: Mapping[FeedbackReason, str] = {
    FeedbackReason.HELPFUL: "Helpful / accurate",
    FeedbackReason.TOO_VAGUE: "Too vague / incomplete",
    FeedbackReason.INACCURATE: "Inaccurate / wrong",
    FeedbackReason.TOO_LONG: "Too long / verbose",
    FeedbackReason.TOO_SHORT: "Too short / missing detail",
    FeedbackReason.WRONG_STYLE: "Wrong tone / style",
    FeedbackReason.OTHER: "Other",
}


def reasons_for_rating(rating: FeedbackRating) -> tuple[FeedbackReason, ...]:
    allowed = REASONS_BY_RATING[rating]
    order = (
        FeedbackReason.HELPFUL,
        FeedbackReason.TOO_VAGUE,
        FeedbackReason.INACCURATE,
        FeedbackReason.TOO_LONG,
        FeedbackReason.TOO_SHORT,
        FeedbackReason.WRONG_STYLE,
        FeedbackReason.OTHER,
    )
    return tuple(r for r in order if r in allowed)


def is_sha256_hex(value: str) -> bool:
    return bool(isinstance(value, str) and _SHA256_RE.fullmatch(value))


def is_uuid_str(value: str) -> bool:
    return bool(isinstance(value, str) and _UUID_RE.fullmatch(value))


def normalize_note(note: str | None) -> str:
    if note is None:
        return ""
    if not isinstance(note, str):
        raise TypeError("note must be a string")
    text = unicodedata.normalize("NFC", note)
    if "\x00" in text:
        text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.rstrip()
    if len(text) > NOTE_MAX_CODEPOINTS:
        raise ValueError(
            f"note exceeds {NOTE_MAX_CODEPOINTS} Unicode code points "
            f"(got {len(text)})"
        )
    return text


def compute_output_sha256(text: str) -> str:
    """Hash the exact rated content (UTF-8 of NFC-normalized text)."""
    normalized = unicodedata.normalize("NFC", text if isinstance(text, str) else "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _id_part(value: str | None) -> str:
    if value is None:
        return ""
    return str(value)


def compute_target_instance_id(
    *,
    surface: str,
    run_id: str,
    subject_type: str,
    subject_id: str,
    module: str,
    artifact_rel_path: str | None,
    output_sha256: str,
    question_id: str | None,
    questions_hash: str | None,
    logical_chart_id: str | None,
    block_id: str | None,
) -> str:
    parts = [
        _id_part(surface),
        _id_part(run_id),
        _id_part(subject_type),
        _id_part(subject_id),
        _id_part(module),
        _id_part(artifact_rel_path),
        _id_part(output_sha256),
        _id_part(question_id),
        _id_part(questions_hash),
        _id_part(logical_chart_id),
        _id_part(block_id),
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def utc_now_z() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def new_uuid4() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class FeedbackTarget:
    surface: str
    block_id: str | None
    placement_id: str | None
    module: str
    run_id: str
    subject_type: str
    subject_id: str
    artifact_rel_path: str | None
    question_id: str | None
    questions_hash: str | None
    logical_chart_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "block_id": self.block_id,
            "placement_id": self.placement_id,
            "module": self.module,
            "run_id": self.run_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "artifact_rel_path": self.artifact_rel_path,
            "question_id": self.question_id,
            "questions_hash": self.questions_hash,
            "logical_chart_id": self.logical_chart_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FeedbackTarget:
        return cls(
            surface=str(data["surface"]),
            block_id=_opt_str(data.get("block_id")),
            placement_id=_opt_str(data.get("placement_id")),
            module=str(data["module"]),
            run_id=str(data["run_id"]),
            subject_type=str(data["subject_type"]),
            subject_id=str(data["subject_id"]),
            artifact_rel_path=_opt_str(data.get("artifact_rel_path")),
            question_id=_opt_str(data.get("question_id")),
            questions_hash=_opt_str(data.get("questions_hash")),
            logical_chart_id=_opt_str(data.get("logical_chart_id")),
        )


@dataclass(frozen=True)
class FeedbackProvenance:
    provider: str | None
    model: str | None
    prompt_version: str | None
    llm_request_sha256: str | None
    output_schema_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "llm_request_sha256": self.llm_request_sha256,
            "output_schema_id": self.output_schema_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> FeedbackProvenance:
        if not isinstance(data, Mapping):
            return cls(None, None, None, None, None)
        return cls(
            provider=_opt_str(data.get("provider")),
            model=_opt_str(data.get("model")),
            prompt_version=_opt_str(data.get("prompt_version")),
            llm_request_sha256=_opt_str(data.get("llm_request_sha256")),
            output_schema_id=_opt_str(
                data.get("output_schema_id")
                if "output_schema_id" in data
                else data.get("schema_id")
            ),
        )

    @classmethod
    def from_artifact_provenance(
        cls, provenance: Mapping[str, Any] | None
    ) -> FeedbackProvenance:
        if not isinstance(provenance, Mapping):
            return cls(None, None, None, None, None)
        schema = provenance.get("schema_id")
        return cls(
            provider=_opt_str(provenance.get("provider")),
            model=_opt_str(provenance.get("model")),
            prompt_version=_opt_str(provenance.get("prompt_version")),
            llm_request_sha256=_opt_str(provenance.get("llm_request_sha256")),
            output_schema_id=_opt_str(schema),
        )


@dataclass(frozen=True)
class FeedbackEvent:
    schema_id: str
    feedback_id: str
    created_at: str
    target_instance_id: str
    submission_token: str
    supersedes_feedback_id: str | None
    rating: str
    reason: str
    note: str
    output_sha256: str
    target: FeedbackTarget
    provenance: FeedbackProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "feedback_id": self.feedback_id,
            "created_at": self.created_at,
            "target_instance_id": self.target_instance_id,
            "submission_token": self.submission_token,
            "supersedes_feedback_id": self.supersedes_feedback_id,
            "rating": self.rating,
            "reason": self.reason,
            "note": self.note,
            "output_sha256": self.output_sha256,
            "target": self.target.to_dict(),
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> FeedbackEvent:
        return cls(
            schema_id=str(data["schema_id"]),
            feedback_id=str(data["feedback_id"]),
            created_at=str(data["created_at"]),
            target_instance_id=str(data["target_instance_id"]),
            submission_token=str(data["submission_token"]),
            supersedes_feedback_id=_opt_str(data.get("supersedes_feedback_id")),
            rating=str(data["rating"]),
            reason=str(data["reason"]),
            note=str(data.get("note") or ""),
            output_sha256=str(data["output_sha256"]),
            target=FeedbackTarget.from_dict(data["target"]),
            provenance=FeedbackProvenance.from_dict(data.get("provenance")),
        )


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def build_event(
    *,
    rating: FeedbackRating | str,
    reason: FeedbackReason | str,
    note: str,
    output_text: str,
    target: FeedbackTarget,
    provenance: FeedbackProvenance | None = None,
    submission_token: str | None = None,
    supersedes_feedback_id: str | None = None,
    feedback_id: str | None = None,
    created_at: str | None = None,
) -> FeedbackEvent:
    rating_s = rating.value if isinstance(rating, FeedbackRating) else str(rating)
    reason_s = reason.value if isinstance(reason, FeedbackReason) else str(reason)
    output_sha = compute_output_sha256(output_text)
    instance_id = compute_target_instance_id(
        surface=target.surface,
        run_id=target.run_id,
        subject_type=target.subject_type,
        subject_id=target.subject_id,
        module=target.module,
        artifact_rel_path=target.artifact_rel_path,
        output_sha256=output_sha,
        question_id=target.question_id,
        questions_hash=target.questions_hash,
        logical_chart_id=target.logical_chart_id,
        block_id=target.block_id,
    )
    return FeedbackEvent(
        schema_id=EVENT_SCHEMA_ID,
        feedback_id=feedback_id or new_uuid4(),
        created_at=created_at or utc_now_z(),
        target_instance_id=instance_id,
        submission_token=submission_token or new_uuid4(),
        supersedes_feedback_id=supersedes_feedback_id,
        rating=rating_s,
        reason=reason_s,
        note=normalize_note(note),
        output_sha256=output_sha,
        target=target,
        provenance=provenance or FeedbackProvenance(None, None, None, None, None),
    )

