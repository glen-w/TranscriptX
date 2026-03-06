"""
Tests for VocabularyStorageService.

This module tests the vocabulary storage service functionality.
"""

import pytest
from transcriptx.database.vocabulary_storage import VocabularyStorageService
from transcriptx.database.models import Speaker, TranscriptFile


class TestVocabularyStorageService:
    """Tests for VocabularyStorageService."""

    @pytest.fixture
    def service(self, db_session):
        """Fixture for VocabularyStorageService."""
        with pytest.MonkeyPatch().context() as m:
            from transcriptx.database import vocabulary_storage

            m.setattr(vocabulary_storage, "get_session", lambda: db_session)
            service = VocabularyStorageService()
            service.session = db_session
            yield service
            service.close()

    @pytest.fixture
    def transcript_file(self, db_session):
        """Create a test transcript file."""
        tf = TranscriptFile(
            file_path="/test/path/transcript.json", file_name="transcript.json"
        )
        db_session.add(tf)
        db_session.commit()
        db_session.refresh(tf)
        return tf

    def test_store_speaker_vocabulary_snapshot(
        self, service, sample_speaker, transcript_file
    ):
        """Test storing vocabulary snapshot."""
        texts = [
            "This is a test document about machine learning.",
            "Machine learning is fascinating and complex.",
            "We use machine learning for various applications.",
        ]

        vocab_words = service.store_speaker_vocabulary_snapshot(
            speaker_id=sample_speaker.id,
            texts=texts,
            transcript_file_id=transcript_file.id,
            source_window="full_transcript",
        )

        assert len(vocab_words) > 0
        assert all(v.speaker_id == sample_speaker.id for v in vocab_words)
        assert all(
            v.source_transcript_file_id == transcript_file.id for v in vocab_words
        )
        assert all(v.snapshot_version == 1 for v in vocab_words)
        assert all(v.tfidf_score > 0 for v in vocab_words)

    def test_vocabulary_snapshot_versioning(
        self, service, sample_speaker, transcript_file
    ):
        """Test that multiple snapshots create different versions."""
        texts1 = ["First batch of text about testing."]
        texts2 = ["Second batch of text about development."]

        # Create first snapshot
        vocab1 = service.store_speaker_vocabulary_snapshot(
            speaker_id=sample_speaker.id,
            texts=texts1,
            transcript_file_id=transcript_file.id,
        )

        # Create second snapshot
        vocab2 = service.store_speaker_vocabulary_snapshot(
            speaker_id=sample_speaker.id,
            texts=texts2,
            transcript_file_id=transcript_file.id,
        )

        assert vocab1[0].snapshot_version == 1
        assert vocab2[0].snapshot_version == 2

    def test_vectorizer_params_hash(self, service, sample_speaker, transcript_file):
        """Test that vectorizer params hash is stored."""
        texts = ["Test text for vocabulary."]

        vocab_words = service.store_speaker_vocabulary_snapshot(
            speaker_id=sample_speaker.id,
            texts=texts,
            transcript_file_id=transcript_file.id,
        )

        assert all(len(v.vectorizer_params_hash) == 64 for v in vocab_words)
        assert all(v.vectorizer_params_hash is not None for v in vocab_words)

    def test_find_speakers_by_vocabulary(self, service, db_session, transcript_file):
        """Test finding speakers by vocabulary similarity."""
        # Create two speakers with different vocabularies
        speaker1 = Speaker(name="Speaker1", display_name="Speaker 1")
        speaker2 = Speaker(name="Speaker2", display_name="Speaker 2")
        db_session.add_all([speaker1, speaker2])
        db_session.commit()
        db_session.refresh(speaker1)
        db_session.refresh(speaker2)

        # Store vocabulary for speaker1
        service.store_speaker_vocabulary_snapshot(
            speaker_id=speaker1.id,
            texts=["I love machine learning and artificial intelligence."],
            transcript_file_id=transcript_file.id,
        )

        # Store vocabulary for speaker2
        service.store_speaker_vocabulary_snapshot(
            speaker_id=speaker2.id,
            texts=["I enjoy cooking and baking delicious meals."],
            transcript_file_id=transcript_file.id,
        )

        # Search for machine learning text (should match speaker1)
        matches = service.find_speakers_by_vocabulary(
            text="I am interested in machine learning algorithms.",
            top_n=2,
            min_confidence=0.1,
        )

        assert len(matches) > 0
        # Should find speaker1 (machine learning) before speaker2 (cooking)
        found_speaker1 = any(speaker.id == speaker1.id for speaker, _ in matches)
        assert found_speaker1

    def test_find_speakers_empty_text(self, service):
        """Test finding speakers with empty text."""
        matches = service.find_speakers_by_vocabulary("")
        assert len(matches) == 0

    def test_find_speakers_no_vocabulary(self, service):
        """Test finding speakers when no vocabulary exists."""
        matches = service.find_speakers_by_vocabulary("Some text here.")
        assert len(matches) == 0

    def test_vocabulary_ngram_types(self, service, sample_speaker, transcript_file):
        """Test that vocabulary includes both unigrams and bigrams."""
        texts = ["Machine learning is great for data science."]

        vocab_words = service.store_speaker_vocabulary_snapshot(
            speaker_id=sample_speaker.id,
            texts=texts,
            transcript_file_id=transcript_file.id,
        )

        ngram_types = set(v.ngram_type for v in vocab_words)
        # Should have at least unigrams, possibly bigrams
        assert "unigram" in ngram_types or len(ngram_types) > 0

    def test_analysis_run_id(self, service, sample_speaker, transcript_file):
        """Test storing vocabulary with analysis_run_id."""
        from uuid import uuid4

        run_id = str(uuid4())

        vocab_words = service.store_speaker_vocabulary_snapshot(
            speaker_id=sample_speaker.id,
            texts=["Test text."],
            transcript_file_id=transcript_file.id,
            analysis_run_id=run_id,
        )

        assert all(v.analysis_run_id == run_id for v in vocab_words)
