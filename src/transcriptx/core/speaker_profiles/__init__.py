"""Longitudinal speaker profiles (Phase 1) — file-backed identity store."""

from __future__ import annotations

from transcriptx.core.speaker_profiles.errors import (
    DuplicateImportIdError,
    ManagedTranscriptResolverError,
    NotManagedTranscriptError,
    SpeakerKeyCollisionError,
    SpeakerProfileContractError,
    SpeakerProfilePathError,
    StaleUpdateError,
    UnresolvedManagedTranscriptError,
)
from transcriptx.core.speaker_profiles.provenance import LinkProvenanceV1
from transcriptx.core.speaker_profiles.resolver import (
    ManagedTranscriptResolver,
    ResolvedManagedTranscript,
)
from transcriptx.core.speaker_profiles.service import SpeakerProfileService, MutationResult
from transcriptx.core.speaker_profiles.versioning import (
    EVENT_SCHEMA_ID,
    LINK_SCHEMA_ID,
    OPERATION_SCHEMA_ID,
    PROFILE_SCHEMA_ID,
    SCHEMA_VERSION,
)

__all__ = [
    "EVENT_SCHEMA_ID",
    "LINK_SCHEMA_ID",
    "LinkProvenanceV1",
    "OPERATION_SCHEMA_ID",
    "PROFILE_SCHEMA_ID",
    "SCHEMA_VERSION",
    "DuplicateImportIdError",
    "ManagedTranscriptResolver",
    "ManagedTranscriptResolverError",
    "MutationResult",
    "NotManagedTranscriptError",
    "ResolvedManagedTranscript",
    "SpeakerKeyCollisionError",
    "SpeakerProfileContractError",
    "SpeakerProfilePathError",
    "SpeakerProfileService",
    "StaleUpdateError",
    "UnresolvedManagedTranscriptError",
]
