"""
DB-backed transcript adapter for legacy module input contract.
"""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.utils.canonicalization import normalize_text, normalize_timestamp
from transcriptx.core.utils.logger import get_logger
from transcriptx.database import get_session
from transcriptx.database.models import TranscriptFile, TranscriptSegment, TranscriptSpeaker

logger = get_logger()


class TranscriptDbAdapter:
    """Reconstruct JSON-like segments from canonical DB tables."""

    def __init__(self) -> None:
        self.session = get_session()

    def _resolve_speaker_display_name(
        self,
        segment: TranscriptSegment,
        transcript_speakers: dict[int, TranscriptSpeaker],
    ) -> str:
        speaker = segment.speaker
        if speaker:
            if speaker.display_name:
                return speaker.display_name
            if speaker.name:
                return speaker.name
            parts = [speaker.first_name, speaker.surname]
            combined = " ".join([p for p in parts if p])
            if combined:
                return combined

        transcript_speaker = transcript_speakers.get(segment.transcript_speaker_id or -1)
        if transcript_speaker:
            return transcript_speaker.display_name or transcript_speaker.speaker_label

        return ""

    def load_segments_by_path(self, transcript_path: str) -> List[Dict[str, Any]]:
        transcript_file = (
            self.session.query(TranscriptFile)
            .filter(TranscriptFile.file_path == transcript_path)
            .first()
        )
        if not transcript_file:
            raise FileNotFoundError(f"Transcript not found in DB: {transcript_path}")
        return self.load_segments_by_file_id(transcript_file.id)

    def load_segments_by_file_id(self, transcript_file_id: int) -> List[Dict[str, Any]]:
        segments = (
            self.session.query(TranscriptSegment)
            .filter(TranscriptSegment.transcript_file_id == transcript_file_id)
            .order_by(
                TranscriptSegment.start_time.asc(),
                TranscriptSegment.segment_index.asc(),
            )
            .all()
        )
        if not segments:
            return []

        transcript_speakers = {
            speaker.id: speaker
            for speaker in (
                self.session.query(TranscriptSpeaker)
                .filter(TranscriptSpeaker.transcript_file_id == transcript_file_id)
                .all()
            )
        }
        speaker_map = {
            speaker_id: speaker.speaker_label
            for speaker_id, speaker in transcript_speakers.items()
        }

        payload: List[Dict[str, Any]] = []
        for segment in segments:
            speaker_display = self._resolve_speaker_display_name(
                segment, transcript_speakers
            )
            speaker_label = speaker_map.get(segment.transcript_speaker_id, "")
            speaker_value = speaker_display or speaker_label
            payload.append(
                {
                    "segment_db_id": segment.id,
                    "segment_uuid": segment.uuid,
                    "segment_index": segment.segment_index,
                    "transcript_file_id": segment.transcript_file_id,
                    "start": float(normalize_timestamp(segment.start_time)),
                    "end": float(normalize_timestamp(segment.end_time)),
                    "speaker": speaker_value,
                    "speaker_display": speaker_display or speaker_value,
                    "speaker_db_id": segment.speaker_id,
                    "transcript_speaker_id": segment.transcript_speaker_id,
                    "text": normalize_text(segment.text),
                }
            )
        return payload

    def close(self) -> None:
        if self.session:
            self.session.close()
