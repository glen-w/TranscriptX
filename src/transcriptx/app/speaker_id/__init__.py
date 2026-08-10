"""Speaker Identification application layer (Theme C Phase −1).

Owns mutation orchestration shared by the legacy Streamlit fragment UI and the
Components v2 workspace bridge. Domain I/O stays in SpeakerStudioController /
MappingService; this package owns stale-identity checks, profile-link
partial-success semantics, summary-cache invalidation, auto-advance /
completion effects, and revisioned command/ack handling.
"""

from __future__ import annotations

from transcriptx.app.speaker_id.protocol import (
    PROTOCOL_VERSION,
    SpeakerIdAck,
    SpeakerIdCommand,
    SpeakerIdEffects,
    SpeakerIdFlash,
    mapping_revision_from_state,
    new_action_id,
    transcript_revision_from_path,
)
from transcriptx.app.speaker_id.service import SpeakerIdActionService

__all__ = [
    "PROTOCOL_VERSION",
    "SpeakerIdAck",
    "SpeakerIdActionService",
    "SpeakerIdCommand",
    "SpeakerIdEffects",
    "SpeakerIdFlash",
    "mapping_revision_from_state",
    "new_action_id",
    "transcript_revision_from_path",
]
