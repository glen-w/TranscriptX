"""Domain errors for speaker profiles."""

from __future__ import annotations


class SpeakerProfileContractError(ValueError):
    """Invalid speaker-profile artifact or identity contract violation."""


class SpeakerProfilePathError(SpeakerProfileContractError):
    """Path escapes speaker_profiles root or violates symlink policy."""


class SpeakerKeyCollisionError(SpeakerProfileContractError):
    """Distinct raw speakers collapse to one normalised local_speaker_key."""


class StaleUpdateError(SpeakerProfileContractError):
    """Optimistic concurrency mismatch on profile content sha256."""


class CorruptLinkError(SpeakerProfileContractError):
    """Live link file exists but is unreadable / invalid (repair required)."""


class RepairRequiredError(SpeakerProfileContractError):
    """Intersecting reads/writes blocked until repair completes."""


class IgnoredSpeakerLinkError(SpeakerProfileContractError):
    """Reject new links while the local speaker key is ignored."""


class LinkConflictError(SpeakerProfileContractError):
    """Occurrence already has a confirmed live link."""


class ActiveOperationError(SpeakerProfileContractError):
    """An incomplete / needs_repair operation blocks this record."""


class ManagedTranscriptResolverError(SpeakerProfileContractError):
    """Fail-closed managed transcript resolution failure."""


class DuplicateImportIdError(ManagedTranscriptResolverError):
    """Same import_id appears on more than one admitted managed sidecar."""


class UnresolvedManagedTranscriptError(ManagedTranscriptResolverError):
    """managed_transcript_id does not resolve to exactly one admitted path."""


class NotManagedTranscriptError(ManagedTranscriptResolverError):
    """Path is outside the managed library or fails admission for linking."""


class StaleConfirmationError(SpeakerProfileContractError):
    """Destructive mutation preconditions no longer match reviewed state."""


class AlreadyCurrentError(SpeakerProfileContractError):
    """Reserved — prefer MutationResult.noop for same-profile / current fp."""


class ProfileAnalyticsNotFoundError(SpeakerProfileContractError):
    """Unknown profile_id for analytics pack."""


class ProfileAnalyticsMergedError(SpeakerProfileContractError):
    """Merged profiles must follow Speakers redirect before pack build."""
