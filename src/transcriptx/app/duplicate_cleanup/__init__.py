"""Library duplicate detection and removal (application layer, no Streamlit)."""

from transcriptx.app.duplicate_cleanup.models import (
    CONFIRM_DELETE_DUPLICATES,
    DuplicateAuthorization,
    DuplicateGroup,
    DuplicateKind,
    DuplicateMember,
    DuplicatePreview,
    DuplicateResult,
    FileFingerprint,
    MemberRole,
    authorization_is_valid,
)
from transcriptx.app.duplicate_cleanup.service import DuplicateCleanupService

__all__ = [
    "CONFIRM_DELETE_DUPLICATES",
    "DuplicateAuthorization",
    "DuplicateCleanupService",
    "DuplicateGroup",
    "DuplicateKind",
    "DuplicateMember",
    "DuplicatePreview",
    "DuplicateResult",
    "FileFingerprint",
    "MemberRole",
    "authorization_is_valid",
]
