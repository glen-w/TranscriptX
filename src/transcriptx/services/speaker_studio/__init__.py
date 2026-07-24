"""
Speaker identification services: UI-agnostic segment index, clip extraction, and speaker mapping.

Used by the web Speaker ID flows and workflows so that
mapping writes and clip generation are consistent and single-source.
"""

from transcriptx.services.speaker_studio.segment_index import (
    SegmentIndexService,
    TranscriptSummary,
    SegmentInfo,
    SpeakerMapStatus,
)
from transcriptx.services.speaker_studio.clip_service import (
    ClipService,
    WarmClipsResult,
)
from transcriptx.services.speaker_studio.mapping_service import (
    SpeakerMappingService,
)
from transcriptx.io.speaker_map_resolver import SpeakerMapState
from transcriptx.services.speaker_studio.controller import SpeakerStudioController

__all__ = [
    "SegmentIndexService",
    "TranscriptSummary",
    "SegmentInfo",
    "SpeakerMapStatus",
    "ClipService",
    "WarmClipsResult",
    "SpeakerMappingService",
    "SpeakerMapState",
    "SpeakerStudioController",
]
