"""Enriched-transcript projections for contextual_emotion."""

from __future__ import annotations

from typing import Any, Mapping

from transcriptx.core.analysis.emotion.projections import build_canonical_ref

CONTEXTUAL_PROJECTION_SEGMENT_FIELDS = (
    "contextual_emotion_label",
    "contextual_emotion_confidence",
    "contextual_emotion_analytical_outcome",
    "contextual_emotion_truncated",
    "contextual_emotion_canonical_ref",
    "contextual_emotion_scored_text_hash",
    "context_emotion",
    "context_emotion_primary",
    "context_emotion_source",
)


def clear_contextual_projection(seg: dict[str, Any]) -> None:
    for field_name in CONTEXTUAL_PROJECTION_SEGMENT_FIELDS:
        seg.pop(field_name, None)
    seg.pop("context_emotion_scores", None)


def project_contextual_segment(
    canonical_row: Mapping[str, Any],
    *,
    artifact_generation_id: str,
    schema_version: str,
    semantics_version: str = "contextual_emotion_v1",
) -> dict[str, Any]:
    row_key = str(canonical_row.get("segment_id") or "")
    label = canonical_row.get("contextual_emotion_label") or ""
    confidence = float(canonical_row.get("contextual_emotion_confidence") or 0.0)
    outcome = canonical_row.get("analytical_outcome")
    truncated = bool(canonical_row.get("truncated"))
    text_hash = canonical_row.get("scored_text_hash")
    ref = build_canonical_ref(
        module_id="contextual_emotion",
        artifact_generation_id=artifact_generation_id,
        schema_version=schema_version,
        semantics_version=semantics_version,
        row_key=row_key,
        row=canonical_row,
    )
    return {
        "segment_id": row_key,
        "evaluation_state": canonical_row.get("evaluation_state"),
        "analytical_outcome": outcome,
        "contextual_emotion_label": label,
        "contextual_emotion_confidence": confidence,
        "truncated": truncated,
        "canonical_ref": ref,
        "contextual_emotion_analytical_outcome": outcome,
        "contextual_emotion_truncated": truncated,
        "contextual_emotion_canonical_ref": ref,
        "contextual_emotion_scored_text_hash": text_hash,
        "context_emotion": label,
        "context_emotion_primary": label,
        "context_emotion_source": "contextual_emotion",
    }


def apply_contextual_projection(
    seg: dict[str, Any],
    projection: Mapping[str, Any],
) -> None:
    clear_contextual_projection(seg)
    for field_name in CONTEXTUAL_PROJECTION_SEGMENT_FIELDS:
        if field_name in projection:
            seg[field_name] = projection[field_name]
