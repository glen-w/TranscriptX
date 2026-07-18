"""Enriched-transcript projections for fine_grained_emotion."""

from __future__ import annotations

from typing import Any, Mapping

from transcriptx.core.analysis.emotion.projections import build_canonical_ref

# Display-only ontology — never stored on analytical canonical rows.
FAMILY_ONTOLOGY_V1 = "fine_grained_family_ontology_v1"
FAMILY_ONTOLOGY: dict[str, str] = {
    "admiration": "positive",
    "amusement": "positive",
    "approval": "positive",
    "caring": "positive",
    "desire": "positive",
    "excitement": "positive",
    "gratitude": "positive",
    "joy": "positive",
    "love": "positive",
    "optimism": "positive",
    "pride": "positive",
    "relief": "positive",
    "anger": "negative",
    "annoyance": "negative",
    "disappointment": "negative",
    "disapproval": "negative",
    "disgust": "negative",
    "embarrassment": "negative",
    "fear": "negative",
    "grief": "negative",
    "nervousness": "negative",
    "remorse": "negative",
    "sadness": "negative",
    "curiosity": "cognitive",
    "realization": "cognitive",
    "surprise": "cognitive",
    "confusion": "cognitive",
    "neutral": "neutral",
}


def display_families_for_labels(labels: list[str]) -> dict[str, str]:
    return {lab: FAMILY_ONTOLOGY.get(lab, "other") for lab in labels}


FINE_GRAINED_PROJECTION_SEGMENT_FIELDS = (
    "fine_grained_emotion_labels",
    "fine_grained_emotion_analytical_outcome",
    "fine_grained_emotion_evaluation_state",
    "fine_grained_emotion_mixed",
    "fine_grained_emotion_qualifying_emotion_count",
    "fine_grained_emotion_truncated",
    "fine_grained_emotion_scored_text_hash",
    "fine_grained_emotion_canonical_ref",
    "fine_grained_emotion_families",
)


def clear_fine_grained_projection(seg: dict[str, Any]) -> None:
    for field_name in FINE_GRAINED_PROJECTION_SEGMENT_FIELDS:
        seg.pop(field_name, None)


def project_fine_grained_segment(
    canonical_row: Mapping[str, Any],
    *,
    artifact_generation_id: str,
    schema_version: str,
    semantics_version: str = "fine_grained_emotion_v1",
) -> dict[str, Any]:
    row_key = str(canonical_row.get("segment_id") or "")
    display = list(canonical_row.get("display_labels") or [])
    ref = build_canonical_ref(
        module_id="fine_grained_emotion",
        artifact_generation_id=artifact_generation_id,
        schema_version=schema_version,
        semantics_version=semantics_version,
        row_key=row_key,
        row=canonical_row,
    )
    return {
        "segment_id": row_key,
        "evaluation_state": canonical_row.get("evaluation_state"),
        "analytical_outcome": canonical_row.get("analytical_outcome"),
        "fine_grained_emotion_labels": display,
        "fine_grained_emotion_analytical_outcome": canonical_row.get(
            "analytical_outcome"
        ),
        "fine_grained_emotion_evaluation_state": canonical_row.get("evaluation_state"),
        "fine_grained_emotion_mixed": bool(canonical_row.get("mixed")),
        "fine_grained_emotion_qualifying_emotion_count": int(
            canonical_row.get("qualifying_emotion_count") or 0
        ),
        "fine_grained_emotion_truncated": bool(canonical_row.get("truncated")),
        "fine_grained_emotion_scored_text_hash": canonical_row.get("scored_text_hash"),
        "fine_grained_emotion_canonical_ref": ref,
        # Display-only; derived at projection time, not analytical canonical.
        "fine_grained_emotion_families": display_families_for_labels(display),
    }


def apply_fine_grained_projection(
    seg: dict[str, Any],
    projection: Mapping[str, Any],
) -> None:
    clear_fine_grained_projection(seg)
    for field_name in FINE_GRAINED_PROJECTION_SEGMENT_FIELDS:
        if field_name in projection:
            seg[field_name] = projection[field_name]
