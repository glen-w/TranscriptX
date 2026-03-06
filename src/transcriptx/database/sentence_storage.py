"""
Sentence Storage Service for TranscriptX Database Integration.

This module provides a service class for storing transcript sentences
in the database, handling sentence splitting, timestamp interpolation,
and speaker identity assignment.
"""

from typing import List, Optional
from uuid import uuid4

from transcriptx.core.utils.logger import get_logger
from transcriptx.database import get_session
from transcriptx.database.models import TranscriptSegment, TranscriptSentence
from transcriptx.utils.text_utils import extract_sentences

logger = get_logger()


class SentenceStorageService:
    """
    Service for storing transcript sentences with speaker_id and timestamps.

    This service handles:
    - Splitting segments into sentences
    - Interpolating timestamps proportionally across sentences
    - Assigning speaker_id to each sentence
    - Storing provenance information (split_method, provenance_version)
    """

    def __init__(self):
        """Initialize the sentence storage service."""
        self.session = get_session()

    def store_sentences_from_segments(
        self, segments: List[TranscriptSegment], analysis_run_id: Optional[str] = None
    ) -> List[TranscriptSentence]:
        """
        Split segments into sentences and store with speaker_id and timestamps.

        Uses extract_sentences() from transcriptx.utils.text_utils to split text.
        Distributes timestamps proportionally across sentences within a segment.

        Note: Proportional timestamp distribution is an MVP approach. Speech rate is
        uneven and punctuation ≠ timing. All sentences created this way will have
        timestamp_estimated=True. Future enhancements can use word-level timestamps
        or WhisperX alignments to set timestamp_estimated=False.

        Args:
            segments: List of TranscriptSegment objects to split into sentences
            analysis_run_id: Optional UUID linking sentences to analysis run

        Returns:
            List of created TranscriptSentence objects

        Raises:
            Exception: For database errors
        """
        try:
            logger.info(f"🔧 Storing sentences from {len(segments)} segments")

            all_sentences = []

            for segment in segments:
                # Extract sentences from segment text
                sentence_texts = extract_sentences(segment.text)

                if not sentence_texts:
                    # If no sentences found, create one sentence from the entire segment
                    sentence_texts = [segment.text] if segment.text.strip() else []

                if not sentence_texts:
                    continue

                # Calculate segment duration
                segment_duration = segment.end_time - segment.start_time
                total_words = sum(len(s.split()) for s in sentence_texts)

                # Distribute timestamps proportionally
                current_time = segment.start_time
                sentences_data = []

                for idx, sentence_text in enumerate(sentence_texts):
                    sentence_words = len(sentence_text.split())

                    # Calculate proportional duration for this sentence
                    if total_words > 0:
                        sentence_duration = (
                            sentence_words / total_words
                        ) * segment_duration
                    else:
                        sentence_duration = segment_duration / len(sentence_texts)

                    sentence_start = current_time
                    sentence_end = current_time + sentence_duration

                    # Create sentence object
                    sentence = TranscriptSentence(
                        uuid=str(uuid4()),
                        transcript_segment_id=segment.id,
                        speaker_id=segment.speaker_id,
                        transcript_speaker_id=segment.transcript_speaker_id,
                        sentence_index=idx,
                        text=sentence_text.strip(),
                        start_time=sentence_start,
                        end_time=sentence_end,
                        word_count=sentence_words,
                        timestamp_estimated=True,  # Always True for proportional interpolation
                        split_method="punctuation",  # Using extract_sentences from text_utils
                        provenance_version=1,
                        analysis_run_id=analysis_run_id,
                    )

                    sentences_data.append(sentence)
                    current_time = sentence_end

                # Bulk insert sentences for this segment
                self.session.add_all(sentences_data)
                all_sentences.extend(sentences_data)

            self.session.commit()
            logger.info(
                f"✅ Stored {len(all_sentences)} sentences from {len(segments)} segments"
            )
            return all_sentences

        except Exception as e:
            logger.error(f"❌ Failed to store sentences: {e}")
            if self.session:
                self.session.rollback()
            raise

    def close(self):
        """Close the database session."""
        if self.session:
            self.session.close()
