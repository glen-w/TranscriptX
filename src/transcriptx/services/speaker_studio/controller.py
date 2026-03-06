"""
SpeakerStudioController: thin orchestrator for Speaker Studio.

Defines the API boundary for the Studio UI (Streamlit, future REST).
All business logic lives in SegmentIndexService, ClipService, SpeakerMappingService;
the controller delegates only.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from transcriptx.services.speaker_studio.segment_index import (
    SegmentIndexService,
    TranscriptSummary,
    SegmentInfo,
)
from transcriptx.services.speaker_studio.clip_service import ClipService
from transcriptx.services.speaker_studio.mapping_service import (
    SpeakerMappingService,
    SpeakerMapState,
)


class SpeakerStudioController:
    """
    Orchestrator for Speaker Studio. Methods map 1:1 to UI actions (and future REST).
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
    ) -> None:
        self._segment_index = SegmentIndexService(data_dir=data_dir)
        self._clip_service = ClipService(data_dir=data_dir)
        self._mapping_service = SpeakerMappingService()

    def list_transcripts(
        self,
        data_dir: Optional[Path] = None,
        *,
        canonical_only: bool = False,
    ) -> List[TranscriptSummary]:
        """List transcripts with speaker-map status for the picker.
        When canonical_only=False (default for UI), includes all .json files
        in data/transcripts that load as segment-bearing transcripts."""
        return self._segment_index.list_transcripts(
            data_dir=data_dir, canonical_only=canonical_only
        )

    def list_segments(self, transcript_path: str) -> List[SegmentInfo]:
        """List segments for a transcript (start, end, text, speaker)."""
        return self._segment_index.list_segments(transcript_path)

    def get_audio_path(self, transcript_path: str) -> Optional[Path]:
        """Resolve audio file for the transcript; None if not found."""
        return self._segment_index.get_transcript_audio_path(transcript_path)

    def get_clip_bytes(
        self,
        transcript_path: str,
        start: float,
        end: float,
        *,
        format: str = "mp3",
    ) -> bytes:
        """Return bytes of the segment clip for playback (e.g. st.audio). Raises if no audio or extract fails."""
        audio_path = self._segment_index.get_transcript_audio_path(transcript_path)
        if not audio_path:
            raise FileNotFoundError(
                f"No audio file found for transcript: {transcript_path}"
            )
        return self._clip_service.get_clip_bytes(
            audio_path,
            start,
            end,
            format=format,
        )

    def get_clip_path(
        self,
        transcript_path: str,
        start: float,
        end: float,
        *,
        format: str = "mp3",
    ) -> Path:
        """Return path to cached clip; useful when caller needs a path. Raises if no audio or extract fails."""
        audio_path = self._segment_index.get_transcript_audio_path(transcript_path)
        if not audio_path:
            raise FileNotFoundError(
                f"No audio file found for transcript: {transcript_path}"
            )
        return self._clip_service.get_clip_path(audio_path, start, end, format=format)

    def apply_mapping_mutation(
        self,
        transcript_path: str,
        diarized_id: str,
        display_name: str,
        *,
        method: str = "web",
    ) -> SpeakerMapState:
        """Assign a display name to a diarized ID. Returns updated mapping state."""
        return self._mapping_service.assign_speaker(
            transcript_path,
            diarized_id,
            display_name,
            method=method,
        )

    def ignore_speaker(
        self,
        transcript_path: str,
        diarized_id: str,
        *,
        method: str = "web",
    ) -> SpeakerMapState:
        """Mark a diarized ID as ignored. Returns updated mapping state."""
        return self._mapping_service.ignore_speaker(
            transcript_path,
            diarized_id,
            method=method,
        )

    def get_mapping_status(self, transcript_path: str) -> SpeakerMapState:
        """Current speaker map and ignored list for the transcript."""
        return self._mapping_service.get_mapping(transcript_path)
