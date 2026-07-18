"""Lightweight enriched-transcript projections for lexical emotion."""

from __future__ import annotations

from typing import Any, Mapping

from transcriptx.core.analysis.emotion_family.canonical_hash import canonical_json_hash

LEXICAL_PROJECTION_SEGMENT_FIELDS = (
    "nrc_emotion",
    "nrc_valence_scores",
    "nrc_emotion_coverage",
    "emotion_evaluation_state",
    "emotion_scored_text_hash",
    "emotion_canonical_ref",
)


def build_canonical_ref(
    *,
    module_id: str,
    artifact_generation_id: str,
    schema_version: str,
    semantics_version: str | None = None,
    row_key: str,
    row: Mapping[str, Any],
) -> dict[str, str]:
    ref: dict[str, str] = {
        "module_id": module_id,
        "artifact_generation_id": artifact_generation_id,
        "schema_version": schema_version,
        "row_key": row_key,
        "integrity_checksum": canonical_json_hash(dict(row)),
        "scored_text_hash": str(row.get("scored_text_hash") or ""),
    }
    if semantics_version is not None:
        ref["semantics_version"] = semantics_version
    return ref


def clear_lexical_projection(seg: dict[str, Any]) -> None:
    for field_name in LEXICAL_PROJECTION_SEGMENT_FIELDS:
        seg.pop(field_name, None)


def project_lexical_segment(
    canonical_row: Mapping[str, Any],
    *,
    artifact_generation_id: str,
    schema_version: str,
    semantics_version: str = "emotion_lexical_v2",
    contributing_preview_limit: int = 8,
) -> dict[str, Any]:
    contributing = list(canonical_row.get("contributing") or [])
    preview = contributing[:contributing_preview_limit]
    row_key = str(canonical_row.get("segment_id") or "")
    return {
        "segment_id": row_key,
        "evaluation_state": canonical_row.get("evaluation_state"),
        "nrc_emotion_coverage": canonical_row.get("coverage"),
        "nrc_emotion": dict(canonical_row.get("emotion_scores") or {}),
        "nrc_valence_scores": dict(canonical_row.get("valence_scores") or {}),
        "emotion_scored_text_hash": canonical_row.get("scored_text_hash"),
        "contributing_words_preview": preview,
        "canonical_ref": build_canonical_ref(
            module_id="emotion",
            artifact_generation_id=artifact_generation_id,
            schema_version=schema_version,
            semantics_version=semantics_version,
            row_key=row_key,
            row=canonical_row,
        ),
    }


def apply_lexical_projection(
    seg: dict[str, Any],
    projection: Mapping[str, Any],
) -> None:
    """Apply lexical projection fields onto a segment (owned fields only)."""
    clear_lexical_projection(seg)
    seg["nrc_emotion"] = projection["nrc_emotion"]
    seg["nrc_valence_scores"] = projection["nrc_valence_scores"]
    seg["nrc_emotion_coverage"] = projection["nrc_emotion_coverage"]
    seg["emotion_evaluation_state"] = projection["evaluation_state"]
    seg["emotion_scored_text_hash"] = projection.get("emotion_scored_text_hash")
    seg["emotion_canonical_ref"] = projection["canonical_ref"]
