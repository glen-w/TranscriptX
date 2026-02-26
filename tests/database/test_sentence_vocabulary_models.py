"""
Tests for sentence, vocabulary, and resolution event models.

This module tests the new database models:
- TranscriptSentence
- SpeakerVocabularyWord
- SpeakerResolutionEvent
"""

import pytest
from uuid import uuid4

from transcriptx.database.models import (
    TranscriptSentence,
    SpeakerVocabularyWord,
    SpeakerResolutionEvent,
    TranscriptFile,
    TranscriptSegment,
)


class TestTranscriptSentence:
    """Tests for TranscriptSentence model."""

    def test_sentence_creation(self, db_session, sample_speaker):
        """Test creating a transcript sentence."""
        # Create transcript file and segment first
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json",
            file_name="transcript.json",
            duration_seconds=100.0,
            segment_count=1,
            speaker_count=1,
        )
        db_session.add(transcript_file)
        db_session.commit()

        segment = TranscriptSegment(
            transcript_file_id=transcript_file.id,
            segment_index=0,
            text="This is a test sentence. And another one.",
            start_time=0.0,
            end_time=5.0,
            speaker_id=sample_speaker.id,
        )
        db_session.add(segment)
        db_session.commit()

        # Create sentence
        sentence = TranscriptSentence(
            transcript_segment_id=segment.id,
            speaker_id=sample_speaker.id,
            sentence_index=0,
            text="This is a test sentence.",
            start_time=0.0,
            end_time=2.5,
            word_count=5,
            timestamp_estimated=True,
            split_method="punctuation",
            provenance_version=1,
        )
        db_session.add(sentence)
        db_session.commit()

        assert sentence.id is not None
        assert sentence.uuid is not None
        assert sentence.text == "This is a test sentence."
        assert sentence.speaker_id == sample_speaker.id
        assert sentence.timestamp_estimated is True
        assert sentence.split_method == "punctuation"
        assert sentence.provenance_version == 1

    def test_sentence_relationships(self, db_session, sample_speaker):
        """Test sentence relationships to segment and speaker."""
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(transcript_file)
        db_session.commit()

        segment = TranscriptSegment(
            transcript_file_id=transcript_file.id,
            segment_index=0,
            text="Test text.",
            start_time=0.0,
            end_time=2.0,
            speaker_id=sample_speaker.id,
        )
        db_session.add(segment)
        db_session.commit()

        sentence = TranscriptSentence(
            transcript_segment_id=segment.id,
            speaker_id=sample_speaker.id,
            sentence_index=0,
            text="Test text.",
            start_time=0.0,
            end_time=2.0,
        )
        db_session.add(sentence)
        db_session.commit()

        # Test relationships
        assert sentence.transcript_segment.id == segment.id
        assert sentence.speaker.id == sample_speaker.id
        assert sentence in segment.sentences
        assert sentence in sample_speaker.transcript_sentences

    def test_sentence_cascade_delete(self, db_session, sample_speaker):
        """Test that sentences are deleted when segment is deleted."""
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(transcript_file)
        db_session.commit()

        segment = TranscriptSegment(
            transcript_file_id=transcript_file.id,
            segment_index=0,
            text="Test text.",
            start_time=0.0,
            end_time=2.0,
            speaker_id=sample_speaker.id,
        )
        db_session.add(segment)
        db_session.commit()

        sentence = TranscriptSentence(
            transcript_segment_id=segment.id,
            speaker_id=sample_speaker.id,
            sentence_index=0,
            text="Test text.",
            start_time=0.0,
            end_time=2.0,
        )
        db_session.add(sentence)
        db_session.commit()

        sentence_id = sentence.id

        # Delete segment
        db_session.delete(segment)
        db_session.commit()

        # Sentence should be deleted
        deleted_sentence = (
            db_session.query(TranscriptSentence).filter_by(id=sentence_id).first()
        )
        assert deleted_sentence is None

    def test_sentence_analysis_run_id(self, db_session, sample_speaker):
        """Test sentence with analysis_run_id."""
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(transcript_file)
        db_session.commit()

        segment = TranscriptSegment(
            transcript_file_id=transcript_file.id,
            segment_index=0,
            text="Test text.",
            start_time=0.0,
            end_time=2.0,
            speaker_id=sample_speaker.id,
        )
        db_session.add(segment)
        db_session.commit()

        run_id = str(uuid4())
        sentence = TranscriptSentence(
            transcript_segment_id=segment.id,
            speaker_id=sample_speaker.id,
            sentence_index=0,
            text="Test text.",
            start_time=0.0,
            end_time=2.0,
            analysis_run_id=run_id,
        )
        db_session.add(sentence)
        db_session.commit()

        assert sentence.analysis_run_id == run_id


class TestSpeakerVocabularyWord:
    """Tests for SpeakerVocabularyWord model."""

    def test_vocabulary_word_creation(self, db_session, sample_speaker):
        """Test creating a vocabulary word."""
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(transcript_file)
        db_session.commit()

        vocab_word = SpeakerVocabularyWord(
            speaker_id=sample_speaker.id,
            word="test",
            tfidf_score=0.85,
            term_frequency=10,
            document_frequency=5,
            ngram_type="unigram",
            source_transcript_file_id=transcript_file.id,
            vectorizer_params_hash="abc123" * 10,  # 64 chars
            source_window="full_transcript",
            snapshot_version=1,
        )
        db_session.add(vocab_word)
        db_session.commit()

        assert vocab_word.id is not None
        assert vocab_word.uuid is not None
        assert vocab_word.word == "test"
        assert vocab_word.tfidf_score == 0.85
        assert vocab_word.speaker_id == sample_speaker.id
        assert vocab_word.snapshot_version == 1

    def test_vocabulary_word_relationships(self, db_session, sample_speaker):
        """Test vocabulary word relationships."""
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(transcript_file)
        db_session.commit()

        vocab_word = SpeakerVocabularyWord(
            speaker_id=sample_speaker.id,
            word="test",
            tfidf_score=0.85,
            vectorizer_params_hash="abc123" * 10,
            snapshot_version=1,
            source_transcript_file_id=transcript_file.id,
        )
        db_session.add(vocab_word)
        db_session.commit()

        assert vocab_word.speaker.id == sample_speaker.id
        assert vocab_word.transcript_file.id == transcript_file.id
        assert vocab_word in sample_speaker.vocabulary_words

    def test_vocabulary_word_unique_constraint(self, db_session, sample_speaker):
        """Test unique constraint on speaker+word+ngram+file+snapshot."""
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(transcript_file)
        db_session.commit()

        params_hash = "abc123" * 10

        # Create first vocabulary word
        vocab1 = SpeakerVocabularyWord(
            speaker_id=sample_speaker.id,
            word="test",
            tfidf_score=0.85,
            ngram_type="unigram",
            source_transcript_file_id=transcript_file.id,
            vectorizer_params_hash=params_hash,
            snapshot_version=1,
        )
        db_session.add(vocab1)
        db_session.commit()

        # Try to create duplicate (should fail)
        vocab2 = SpeakerVocabularyWord(
            speaker_id=sample_speaker.id,
            word="test",
            tfidf_score=0.90,
            ngram_type="unigram",
            source_transcript_file_id=transcript_file.id,
            vectorizer_params_hash=params_hash,
            snapshot_version=1,
        )
        db_session.add(vocab2)

        with pytest.raises(Exception):  # Should raise IntegrityError
            db_session.commit()

        db_session.rollback()

    def test_vocabulary_word_snapshot_versioning(self, db_session, sample_speaker):
        """Test that different snapshot versions can have same word."""
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(transcript_file)
        db_session.commit()

        params_hash = "abc123" * 10

        # Create vocabulary word with snapshot version 1
        vocab1 = SpeakerVocabularyWord(
            speaker_id=sample_speaker.id,
            word="test",
            tfidf_score=0.85,
            ngram_type="unigram",
            source_transcript_file_id=transcript_file.id,
            vectorizer_params_hash=params_hash,
            snapshot_version=1,
        )
        db_session.add(vocab1)
        db_session.commit()

        # Create same word with snapshot version 2 (should succeed)
        vocab2 = SpeakerVocabularyWord(
            speaker_id=sample_speaker.id,
            word="test",
            tfidf_score=0.90,
            ngram_type="unigram",
            source_transcript_file_id=transcript_file.id,
            vectorizer_params_hash=params_hash,
            snapshot_version=2,
        )
        db_session.add(vocab2)
        db_session.commit()

        assert vocab1.snapshot_version == 1
        assert vocab2.snapshot_version == 2
        assert vocab1.id != vocab2.id


class TestSpeakerResolutionEvent:
    """Tests for SpeakerResolutionEvent model."""

    def test_resolution_event_creation(self, db_session, sample_speaker):
        """Test creating a resolution event."""
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(transcript_file)
        db_session.commit()

        event = SpeakerResolutionEvent(
            transcript_file_id=transcript_file.id,
            speaker_id=sample_speaker.id,
            diarized_label="SPEAKER_01",
            method="vocabulary_match",
            confidence=0.85,
            evidence_json={"top_terms": ["test", "example"]},
        )
        db_session.add(event)
        db_session.commit()

        assert event.id is not None
        assert event.diarized_label == "SPEAKER_01"
        assert event.method == "vocabulary_match"
        assert event.confidence == 0.85
        assert event.speaker_id == sample_speaker.id

    def test_resolution_event_unresolved(self, db_session):
        """Test resolution event with NULL speaker_id (unresolved)."""
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(transcript_file)
        db_session.commit()

        event = SpeakerResolutionEvent(
            transcript_file_id=transcript_file.id,
            speaker_id=None,  # Unresolved
            diarized_label="SPEAKER_99",
            method="new_speaker",
            confidence=0.0,
            evidence_json={},
        )
        db_session.add(event)
        db_session.commit()

        assert event.speaker_id is None
        assert event.method == "new_speaker"

    def test_resolution_event_relationships(self, db_session, sample_speaker):
        """Test resolution event relationships."""
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(transcript_file)
        db_session.commit()

        event = SpeakerResolutionEvent(
            transcript_file_id=transcript_file.id,
            speaker_id=sample_speaker.id,
            diarized_label="SPEAKER_01",
            method="canonical_id",
            confidence=1.0,
            evidence_json={},
        )
        db_session.add(event)
        db_session.commit()

        assert event.transcript_file.id == transcript_file.id
        assert event.speaker.id == sample_speaker.id
        assert event in transcript_file.resolution_events
        assert event in sample_speaker.resolution_events

    def test_resolution_event_analysis_run_id(self, db_session, sample_speaker):
        """Test resolution event with analysis_run_id."""
        transcript_file = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(transcript_file)
        db_session.commit()

        run_id = str(uuid4())
        event = SpeakerResolutionEvent(
            transcript_file_id=transcript_file.id,
            speaker_id=sample_speaker.id,
            diarized_label="SPEAKER_01",
            method="vocabulary_match",
            confidence=0.85,
            evidence_json={},
            analysis_run_id=run_id,
        )
        db_session.add(event)
        db_session.commit()

        assert event.analysis_run_id == run_id
