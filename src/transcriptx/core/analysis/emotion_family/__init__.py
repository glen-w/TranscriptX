"""Emotion-family shared contracts: hashing, run status, fingerprints, stores."""

from __future__ import annotations

from transcriptx.core.analysis.emotion_family.canonical_hash import (
    CANONICAL_JSON_HASH_V1,
    canonical_json_dumps,
    canonical_json_hash,
    quantize_float_str,
)
from transcriptx.core.analysis.emotion_family.consumer_contracts import (
    OptionalProducerContract,
    evaluate_optional_producer,
)
from transcriptx.core.analysis.emotion_family.errors import (
    EmotionFamilyGenerationConflictError,
    EmotionFamilyGenerationExistsError,
    EmotionFamilyGenerationIncompleteError,
    EmotionFamilyGenerationValidationError,
    EmotionFamilyPersistError,
    EmotionFamilySchemaError,
    EmotionFamilyUnsafeIdentifierError,
)
from transcriptx.core.analysis.emotion_family.fingerprints import (
    build_aggregation_settings,
    build_compatibility_payload,
    build_display_fingerprint,
    build_runtime_metadata,
    build_text_source_payload,
    compatibility_fingerprint,
    library_versions,
    segment_text_hash,
    speaker_identity_digest,
    text_source_digest,
    timeline_identity_digest,
)
from transcriptx.core.analysis.emotion_family.generational_store import (
    ArtifactGenerationIndex,
    activate_complete_generation,
    persist_generation,
    persist_generation_from_results,
    quarantine_orphaned_generations,
    record_attempt,
    record_attempt_only,
    resolve_canonical_ref,
    should_activate_generation,
    update_enriched_projection_status,
)
from transcriptx.core.analysis.emotion_family.persist import (
    apply_pending_projections,
    persist_canonical_then_enrich,
    repair_enriched_projections,
)
from transcriptx.core.analysis.emotion_family.language import (
    LANGUAGE_POLICY_V1,
    extract_transcript_metadata,
    resolve_segment_language,
)
from transcriptx.core.analysis.emotion_family.run_status import (
    AnalyticalOutcome,
    EvaluationState,
    RunStatus,
    derive_run_status_from_rows,
    derive_usable_output,
)
from transcriptx.core.analysis.emotion_family.source_identity import (
    SOURCE_IDENTITY_POLICY_V1,
    ensure_segment_ids,
)

__all__ = [
    "AnalyticalOutcome",
    "ArtifactGenerationIndex",
    "CANONICAL_JSON_HASH_V1",
    "EmotionFamilyGenerationConflictError",
    "EmotionFamilyGenerationExistsError",
    "EmotionFamilyGenerationIncompleteError",
    "EmotionFamilyGenerationValidationError",
    "EmotionFamilyPersistError",
    "EmotionFamilySchemaError",
    "EmotionFamilyUnsafeIdentifierError",
    "EvaluationState",
    "LANGUAGE_POLICY_V1",
    "OptionalProducerContract",
    "RunStatus",
    "SOURCE_IDENTITY_POLICY_V1",
    "activate_complete_generation",
    "build_aggregation_settings",
    "build_compatibility_payload",
    "build_display_fingerprint",
    "build_runtime_metadata",
    "build_text_source_payload",
    "canonical_json_dumps",
    "canonical_json_hash",
    "compatibility_fingerprint",
    "derive_run_status_from_rows",
    "derive_usable_output",
    "ensure_segment_ids",
    "evaluate_optional_producer",
    "extract_transcript_metadata",
    "library_versions",
    "persist_canonical_then_enrich",
    "persist_generation",
    "persist_generation_from_results",
    "apply_pending_projections",
    "quantize_float_str",
    "quarantine_orphaned_generations",
    "record_attempt",
    "record_attempt_only",
    "repair_enriched_projections",
    "resolve_canonical_ref",
    "resolve_segment_language",
    "segment_text_hash",
    "should_activate_generation",
    "speaker_identity_digest",
    "text_source_digest",
    "timeline_identity_digest",
    "update_enriched_projection_status",
]
