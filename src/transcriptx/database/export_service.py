"""
DB to JSON export service for transcripts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.database import get_session
from transcriptx.database.models import (
    TranscriptFile,
    TranscriptSegment,
    TranscriptSpeaker,
)

logger = get_logger()


class TranscriptExportService:
    """Export canonical transcript data from DB to JSON format."""

    def __init__(self):
        self.session = get_session()

    def export_transcript(
        self, transcript_file_id: int, output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        transcript_file = (
            self.session.query(TranscriptFile)
            .filter(TranscriptFile.id == transcript_file_id)
            .first()
        )
        if not transcript_file:
            raise ValueError(f"TranscriptFile {transcript_file_id} not found")

        speakers = (
            self.session.query(TranscriptSpeaker)
            .filter(TranscriptSpeaker.transcript_file_id == transcript_file_id)
            .all()
        )
        speaker_map = {speaker.id: speaker.speaker_label for speaker in speakers}

        segments = (
            self.session.query(TranscriptSegment)
            .filter(TranscriptSegment.transcript_file_id == transcript_file_id)
            .order_by(
                TranscriptSegment.start_time.asc(),
                TranscriptSegment.segment_index.asc(),
            )
            .all()
        )

        payload_segments: List[Dict[str, Any]] = []
        for segment in segments:
            payload_segments.append(
                {
                    "start": segment.start_time,
                    "end": segment.end_time,
                    "speaker": speaker_map.get(segment.transcript_speaker_id, ""),
                    "text": segment.text,
                }
            )

        payload: Dict[str, Any] = {
            "metadata": transcript_file.file_metadata or {},
            "segments": payload_segments,
        }

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
            logger.info(f"✅ Exported transcript {transcript_file_id} to {output_path}")

        return payload

    def close(self) -> None:
        if self.session:
            self.session.close()
