"""
Speaker Studio services: UI-agnostic segment index, clip extraction, and speaker mapping.

Used by both CLI (identify speakers) and Speaker Studio (Streamlit) so that
mapping writes and clip generation are consistent and single-source.
"""

from transcriptx.services.speaker_studio.segment_index import (
    SegmentIndexService,
    TranscriptSummary,
    SegmentInfo,
    SpeakerMapStatus,
)
from transcriptx.services.speaker_studio.clip_service import ClipService
from transcriptx.services.speaker_studio.mapping_service import (
    SpeakerMappingService,
    SpeakerMapState,
)
from transcriptx.services.speaker_studio.controller import SpeakerStudioController

__all__ = [
    "SegmentIndexService",
    "TranscriptSummary",
    "SegmentInfo",
    "SpeakerMapStatus",
    "ClipService",
    "SpeakerMappingService",
    "SpeakerMapState",
    "SpeakerStudioController",
]
