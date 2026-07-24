"""Strict validation for LLM feedback events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from transcriptx.core.llm_feedback.errors import (
    LlmFeedbackPathError,
    LlmFeedbackValidationError,
)
from transcriptx.core.llm_feedback.models import (
    EVENT_SCHEMA_ID,
    REASONS_BY_RATING,
    FeedbackEvent,
    FeedbackProvenance,
    FeedbackRating,
    FeedbackReason,
    FeedbackSurface,
    FeedbackTarget,
    SubjectType,
    is_sha256_hex,
    is_uuid_str,
    normalize_note,
)
from transcriptx.core.llm_feedback.path_safety import assert_safe_artifact_relpath


def _require_nonempty_str(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LlmFeedbackValidationError(f"{field} must be a non-empty string")
    return value.strip()


def _parse_created_at(value: str) -> str:
    raw = _require_nonempty_str(value, "created_at")
    candidate = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise LlmFeedbackValidationError(
            f"created_at must be ISO-8601 UTC: {raw!r}"
        ) from exc
    if dt.tzinfo is None:
        raise LlmFeedbackValidationError("created_at must be timezone-aware UTC")
    offset = dt.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise LlmFeedbackValidationError("created_at must be UTC (Z / +00:00)")
    return (
        dt.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def validate_rating_reason(rating: str, reason: str) -> tuple[str, str]:
    try:
        rating_e = FeedbackRating(rating)
    except ValueError as exc:
        raise LlmFeedbackValidationError(f"invalid rating: {rating!r}") from exc
    try:
        reason_e = FeedbackReason(reason)
    except ValueError as exc:
        raise LlmFeedbackValidationError(f"invalid reason: {reason!r}") from exc
    if reason_e not in REASONS_BY_RATING[rating_e]:
        raise LlmFeedbackValidationError(
            f"reason {reason_e.value!r} is not allowed for rating {rating_e.value!r}"
        )
    return rating_e.value, reason_e.value


def validate_target(target: FeedbackTarget | Mapping[str, Any]) -> FeedbackTarget:
    t = (
        target
        if isinstance(target, FeedbackTarget)
        else FeedbackTarget.from_dict(target)
    )

    try:
        surface = FeedbackSurface(t.surface)
    except ValueError as exc:
        raise LlmFeedbackValidationError(f"invalid surface: {t.surface!r}") from exc
    try:
        SubjectType(t.subject_type)
    except ValueError as exc:
        raise LlmFeedbackValidationError(
            f"invalid subject_type: {t.subject_type!r}"
        ) from exc

    _require_nonempty_str(t.module, "target.module")
    _require_nonempty_str(t.run_id, "target.run_id")
    _require_nonempty_str(t.subject_id, "target.subject_id")

    if t.artifact_rel_path is not None:
        try:
            assert_safe_artifact_relpath(t.artifact_rel_path)
        except LlmFeedbackPathError as exc:
            raise LlmFeedbackValidationError(str(exc)) from exc

    if t.questions_hash is not None:
        h = t.questions_hash.strip().lower()
        if not h or any(c not in "0123456789abcdef" for c in h):
            raise LlmFeedbackValidationError("questions_hash must be lowercase hex")

    if surface in (FeedbackSurface.INSIGHTS_BLOCK, FeedbackSurface.OVERVIEW_HERO):
        if not t.block_id:
            raise LlmFeedbackValidationError(f"{surface.value} requires block_id")
        if not t.artifact_rel_path:
            raise LlmFeedbackValidationError(
                f"{surface.value} requires artifact_rel_path"
            )
    elif surface == FeedbackSurface.CUSTOM_QA_ANSWER:
        if not t.block_id:
            raise LlmFeedbackValidationError("custom_qa_answer requires block_id")
        if not t.artifact_rel_path:
            raise LlmFeedbackValidationError(
                "custom_qa_answer requires artifact_rel_path"
            )
        if not t.question_id:
            raise LlmFeedbackValidationError("custom_qa_answer requires question_id")
        if not t.questions_hash:
            raise LlmFeedbackValidationError("custom_qa_answer requires questions_hash")
    elif surface == FeedbackSurface.CHART_CAPTION:
        if not t.logical_chart_id:
            raise LlmFeedbackValidationError("chart_caption requires logical_chart_id")
        if t.module != "chart_descriptions":
            raise LlmFeedbackValidationError(
                "chart_caption module must be chart_descriptions"
            )

    if t.questions_hash is not None:
        return FeedbackTarget(
            surface=t.surface,
            block_id=t.block_id,
            placement_id=t.placement_id,
            module=t.module,
            run_id=t.run_id,
            subject_type=t.subject_type,
            subject_id=t.subject_id,
            artifact_rel_path=t.artifact_rel_path,
            question_id=t.question_id,
            questions_hash=t.questions_hash.strip().lower(),
            logical_chart_id=t.logical_chart_id,
        )
    return t


def validate_provenance(
    prov: FeedbackProvenance | Mapping[str, Any] | None,
) -> FeedbackProvenance:
    p = (
        prov
        if isinstance(prov, FeedbackProvenance)
        else FeedbackProvenance.from_dict(prov)
    )
    if p.llm_request_sha256 is not None and not is_sha256_hex(p.llm_request_sha256):
        raise LlmFeedbackValidationError(
            "provenance.llm_request_sha256 must be 64 lowercase hex"
        )
    return p


def validate_event(event: FeedbackEvent | Mapping[str, Any]) -> FeedbackEvent:
    if isinstance(event, Mapping):
        if event.get("schema_id") != EVENT_SCHEMA_ID:
            raise LlmFeedbackValidationError(f"schema_id must be {EVENT_SCHEMA_ID!r}")
        ev = FeedbackEvent.from_dict(event)
    else:
        ev = event

    if ev.schema_id != EVENT_SCHEMA_ID:
        raise LlmFeedbackValidationError(f"schema_id must be {EVENT_SCHEMA_ID!r}")
    if not is_uuid_str(ev.feedback_id):
        raise LlmFeedbackValidationError("feedback_id must be a UUID")
    if not is_uuid_str(ev.submission_token):
        raise LlmFeedbackValidationError("submission_token must be a UUID")
    if ev.supersedes_feedback_id is not None and not is_uuid_str(
        ev.supersedes_feedback_id
    ):
        raise LlmFeedbackValidationError(
            "supersedes_feedback_id must be a UUID or null"
        )
    created = _parse_created_at(ev.created_at)
    if not is_sha256_hex(ev.output_sha256):
        raise LlmFeedbackValidationError("output_sha256 must be 64 lowercase hex")
    if not is_sha256_hex(ev.target_instance_id):
        raise LlmFeedbackValidationError("target_instance_id must be 64 lowercase hex")
    rating, reason = validate_rating_reason(ev.rating, ev.reason)
    try:
        note = normalize_note(ev.note)
    except (TypeError, ValueError) as exc:
        raise LlmFeedbackValidationError(str(exc)) from exc
    target = validate_target(ev.target)
    provenance = validate_provenance(ev.provenance)

    return FeedbackEvent(
        schema_id=EVENT_SCHEMA_ID,
        feedback_id=str(ev.feedback_id),
        created_at=created,
        target_instance_id=ev.target_instance_id,
        submission_token=str(ev.submission_token),
        supersedes_feedback_id=ev.supersedes_feedback_id,
        rating=rating,
        reason=reason,
        note=note,
        output_sha256=ev.output_sha256,
        target=target,
        provenance=provenance,
    )
