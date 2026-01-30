"""
Transcript ingestion service for canonical DB storage.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from transcriptx.core.utils.canonicalization import (
    SCHEMA_VERSION,
    SENTENCE_SCHEMA_VERSION,
    compute_source_hash,
    compute_transcript_content_hash,
    normalize_text,
    normalize_timestamp,
)
from transcriptx.core.utils.logger import get_logger
from transcriptx.database import get_session
from transcriptx.database.models import (
    TranscriptFile,
    TranscriptSegment,
    TranscriptSpeaker,
)
from transcriptx.database.repositories import TranscriptSpeakerRepository
from transcriptx.database.sentence_storage import SentenceStorageService
from transcriptx.database.migrations import require_up_to_date_schema

logger = get_logger()


class TranscriptIngestionService:
    """DB-first transcript ingestion with immutable content hashing."""

    def __init__(self) -> None:
        require_up_to_date_schema()
        self.session = get_session()
        self.speaker_repo = TranscriptSpeakerRepository(self.session)

    def ingest_transcript(
        self,
        transcript_path: str,
        source_uri: Optional[str] = None,
        audio_file_path: Optional[str] = None,
        allow_reimport: bool = True,
        store_segments: bool = False,
    ) -> TranscriptFile:
        """
        Ingest transcript metadata into the DB.

        By default, stores only transcript metadata and speaker labels. Segment and
        sentence storage is optional and only enabled when store_segments=True.
        """
        transcript_path_obj = Path(transcript_path)
        if not transcript_path_obj.exists():
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")

        with open(transcript_path, "r", encoding="utf-8") as handle:
            transcript_data = json.load(handle)

        segments = transcript_data.get("segments", [])
        if not segments:
            raise ValueError("No segments found in transcript data")

        content_hash = compute_transcript_content_hash(segments)
        existing = (
            self.session.query(TranscriptFile)
            .filter(
                TranscriptFile.transcript_content_hash == content_hash,
                TranscriptFile.schema_version == SCHEMA_VERSION,
            )
            .first()
        )
        if existing:
            logger.info(
                f"📋 Found existing transcript for content hash {content_hash[:12]}..."
            )
            return existing

        # Create transcript file record
        duration_seconds = max(seg.get("end", 0.0) for seg in segments)
        speaker_labels = []
        for seg in segments:
            label = seg.get("speaker")
            if label and label not in speaker_labels:
                speaker_labels.append(label)

        transcript_file = TranscriptFile(
            file_path=str(transcript_path_obj.resolve()),
            file_name=transcript_path_obj.name,
            audio_file_path=str(audio_file_path) if audio_file_path else None,
            source_uri=source_uri,
            import_timestamp=datetime.utcnow(),
            duration_seconds=duration_seconds,
            segment_count=len(segments),
            speaker_count=len(speaker_labels),
            transcript_content_hash=content_hash,
            schema_version=SCHEMA_VERSION,
            sentence_schema_version=SENTENCE_SCHEMA_VERSION,
            source_hash=compute_source_hash(transcript_path),
            file_metadata=transcript_data.get("metadata", {}),
        )
        self.session.add(transcript_file)
        self.session.flush()

        # Create transcript-scoped speakers
        speaker_map: Dict[str, TranscriptSpeaker] = {}
        for order, label in enumerate(speaker_labels):
            speaker_map[label] = self.speaker_repo.create_transcript_speaker(
                transcript_file_id=transcript_file.id,
                speaker_label=str(label),
                speaker_order=order,
                display_name=str(label),
            )

        stored_segments: List[TranscriptSegment] = []
        if store_segments:
            # Insert segments only when explicitly requested (optional DB cache)
            for index, segment in enumerate(segments):
                speaker_label = segment.get("speaker")
                transcript_speaker = (
                    speaker_map.get(str(speaker_label)) if speaker_label else None
                )
                start = float(normalize_timestamp(segment.get("start", 0.0)))
                end = float(normalize_timestamp(segment.get("end", 0.0)))
                text = normalize_text(segment.get("text", ""))

                stored_segments.append(
                    TranscriptSegment(
                        transcript_file_id=transcript_file.id,
                        transcript_speaker_id=(
                            transcript_speaker.id if transcript_speaker else None
                        ),
                        segment_index=index,
                        text=text,
                        start_time=start,
                        end_time=end,
                        duration=end - start,
                        word_count=len(text.split()),
                    )
                )

            self.session.add_all(stored_segments)
            self.session.flush()

            # Store sentences deterministically from segments
            sentence_service = SentenceStorageService()
            try:
                sentence_service.store_sentences_from_segments(stored_segments)
            finally:
                sentence_service.close()

        self.session.commit()
        if store_segments:
            logger.info(
                f"✅ Ingested transcript {transcript_file.id} with {len(stored_segments)} segments"
            )
        else:
            logger.info(f"✅ Ingested transcript {transcript_file.id} (metadata only)")
        return transcript_file

    def close(self) -> None:
        if self.session:
            self.session.close()
