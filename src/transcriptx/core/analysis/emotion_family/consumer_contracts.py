"""Explicit optional producer contracts for contagion / affect_tension."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from transcriptx.core.analysis.emotion_family.fingerprints import segment_text_hash


@dataclass(frozen=True)
class OptionalProducerContract:
    producer_module_id: str
    accepted_schema_versions: tuple[str, ...]
    accepted_semantics_versions: tuple[str, ...]
    required_run_status: str = "complete"
    required_usable_output: bool = True
    required_segments_scored_min: int = 1
    required_projection_fields: tuple[str, ...] = ()


@dataclass
class OptionalProducerEvaluation:
    satisfied: bool
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


def evaluate_optional_producer(
    contract: OptionalProducerContract,
    *,
    selected: bool,
    artifact: Mapping[str, Any] | None,
) -> OptionalProducerEvaluation:
    """
    Evaluate whether a producer artifact satisfies an optional consumer contract.

    Reasons: not_selected | dependency_failed | dependency_partial |
    dependency_incompatible | dependency_not_applicable | ok
    """
    if not selected:
        return OptionalProducerEvaluation(False, "not_selected")

    if artifact is None:
        return OptionalProducerEvaluation(False, "dependency_failed", {"missing": True})

    producer_id = str(
        artifact.get("module_id")
        or artifact.get("module_name")
        or artifact.get("producer_module_id")
        or ""
    ).strip()
    if not producer_id:
        return OptionalProducerEvaluation(
            False,
            "dependency_incompatible",
            {
                "field": "producer_module_id",
                "expected": contract.producer_module_id,
                "got": "",
                "missing_module_id": True,
            },
        )
    if producer_id != contract.producer_module_id:
        return OptionalProducerEvaluation(
            False,
            "dependency_incompatible",
            {
                "field": "producer_module_id",
                "expected": contract.producer_module_id,
                "got": producer_id,
            },
        )

    run_status = str(artifact.get("run_status") or "")
    if run_status == "partial":
        return OptionalProducerEvaluation(False, "dependency_partial")
    if run_status in {"failed", "skipped"}:
        return OptionalProducerEvaluation(
            False, "dependency_failed", {"run_status": run_status}
        )

    schema = str(artifact.get("schema_version") or "")
    semantics = str(artifact.get("semantics_version") or "")
    if schema not in contract.accepted_schema_versions:
        return OptionalProducerEvaluation(
            False,
            "dependency_incompatible",
            {"field": "schema_version", "got": schema},
        )
    if semantics not in contract.accepted_semantics_versions:
        return OptionalProducerEvaluation(
            False,
            "dependency_incompatible",
            {"field": "semantics_version", "got": semantics},
        )

    usable = bool(artifact.get("usable_output"))
    scored = int(artifact.get("segments_scored") or 0)
    if run_status != contract.required_run_status or (
        contract.required_usable_output and not usable
    ):
        if scored < contract.required_segments_scored_min:
            return OptionalProducerEvaluation(
                False,
                "dependency_not_applicable",
                {"segments_scored": scored, "run_status": run_status},
            )
        return OptionalProducerEvaluation(
            False,
            "dependency_failed",
            {"run_status": run_status, "usable_output": usable},
        )

    if scored < contract.required_segments_scored_min:
        return OptionalProducerEvaluation(
            False,
            "dependency_not_applicable",
            {"segments_scored": scored},
        )

    projections = artifact.get("projection_fields") or artifact.get("required_fields")
    if contract.required_projection_fields:
        sample = artifact.get("sample_projection") or {}
        if sample:
            missing = [
                f for f in contract.required_projection_fields if f not in sample
            ]
        elif isinstance(projections, (list, tuple)):
            present = set(projections)
            missing = [
                f for f in contract.required_projection_fields if f not in present
            ]
        else:
            return OptionalProducerEvaluation(
                False,
                "dependency_incompatible",
                {"missing_projection_evidence": True},
            )
        if missing:
            return OptionalProducerEvaluation(
                False,
                "dependency_incompatible",
                {"missing_projection_fields": missing},
            )

    return OptionalProducerEvaluation(True, "ok")


# Enriched-segment projection fields owned by the contextual_emotion producer.
# Full probability vectors live only in the canonical generational store.
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


def merge_contextual_projection(
    segments: Sequence[dict],
    producer_artifact: Mapping[str, Any],
) -> int:
    """
    Copy contextual_emotion projection fields onto consumer segments.

    Only source segments carrying explicit provenance
    (context_emotion_source == 'contextual_emotion') are merged. Matches by
    unique segment id and requires scored_text_hash against consumer text.
    Stale refs (generation_id != producer artifact generation) are cleared.
    No timestamp fallback. Returns the number of segments carrying the
    contextual projection after the merge.
    """
    active_generation = str(producer_artifact.get("artifact_generation_id") or "")
    source_segments = producer_artifact.get("segments_with_contextual_emotion") or []
    by_id: dict[str, Mapping[str, Any]] = {}
    for src in source_segments:
        if src.get("context_emotion_source") != "contextual_emotion":
            continue
        sid = src.get("id") or src.get("segment_id")
        if sid is not None and str(sid).strip():
            by_id[str(sid)] = src

    merged = 0
    for seg in segments:
        if seg.get("context_emotion_source") == "contextual_emotion":
            ref = seg.get("contextual_emotion_canonical_ref") or {}
            ref_gen = str(ref.get("artifact_generation_id") or "")
            expected = seg.get("contextual_emotion_scored_text_hash")
            stale_generation = bool(
                active_generation and ref_gen and ref_gen != active_generation
            )
            if (
                stale_generation
                or not expected
                or expected != segment_text_hash(seg.get("text"))
            ):
                for field_name in CONTEXTUAL_PROJECTION_SEGMENT_FIELDS:
                    seg.pop(field_name, None)
                continue
            merged += 1
            continue
        sid = seg.get("id") or seg.get("segment_id")
        if sid is None:
            continue
        src = by_id.get(str(sid))
        if src is None:
            continue
        expected = src.get("contextual_emotion_scored_text_hash")
        if not expected or expected != segment_text_hash(seg.get("text")):
            continue
        ref = src.get("contextual_emotion_canonical_ref") or {}
        ref_gen = str(ref.get("artifact_generation_id") or "")
        if active_generation and ref_gen and ref_gen != active_generation:
            continue
        for field_name in CONTEXTUAL_PROJECTION_SEGMENT_FIELDS:
            if field_name in src:
                seg[field_name] = src[field_name]
        merged += 1
    return merged


# Frozen consumer contracts used by contagion / affect_tension
CONTEXTUAL_EMOTION_FOR_CONTAGION = OptionalProducerContract(
    producer_module_id="contextual_emotion",
    accepted_schema_versions=("contextual_emotion_result_schema_v2",),
    accepted_semantics_versions=("contextual_emotion_v1",),
    required_projection_fields=(
        "segment_id",
        "evaluation_state",
        "analytical_outcome",
        "contextual_emotion_label",
        "contextual_emotion_confidence",
        "truncated",
        "canonical_ref",
    ),
)

CONTEXTUAL_EMOTION_FOR_AFFECT_TENSION = CONTEXTUAL_EMOTION_FOR_CONTAGION

LEXICAL_EMOTION_FOR_CONTAGION = OptionalProducerContract(
    producer_module_id="emotion",
    accepted_schema_versions=("emotion_result_schema_v2",),
    accepted_semantics_versions=("emotion_lexical_v2",),
    required_projection_fields=(
        "segment_id",
        "evaluation_state",
        "nrc_emotion",
        "nrc_emotion_coverage",
        "emotion_scored_text_hash",
        "canonical_ref",
    ),
)
