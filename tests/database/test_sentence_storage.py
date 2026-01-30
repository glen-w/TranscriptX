"""
Tests for SentenceStorageService.

This module tests the sentence storage service functionality.
"""

import pytest
from transcriptx.database.sentence_storage import SentenceStorageService
from transcriptx.database.models import TranscriptFile, TranscriptSegment, Speaker


class TestSentenceStorageService:
    """Tests for SentenceStorageService."""
    
    @pytest.fixture
    def service(self, db_session):
        """Fixture for SentenceStorageService."""
        # Patch get_session to return our test session
        with pytest.MonkeyPatch().context() as m:
            from transcriptx.database import sentence_storage
            m.setattr(sentence_storage, 'get_session', lambda: db_session)
            service = SentenceStorageService()
            service.session = db_session
            yield service
            service.close()
    
    @pytest.fixture
    def transcript_file(self, db_session):
        """Create a test transcript file."""
        tf = TranscriptFile(
            file_path="/test/path/transcript.json",
            file_name="transcript.json",
            duration_seconds=100.0,
            segment_count=2,
            speaker_count=1
        )
        db_session.add(tf)
        db_session.commit()
        db_session.refresh(tf)
        return tf
    
    @pytest.fixture
    def sample_segments(self, db_session, transcript_file, sample_speaker):
        """Create sample segments."""
        segments = [
            TranscriptSegment(
                transcript_file_id=transcript_file.id,
                segment_index=0,
                text="This is the first sentence. This is the second sentence.",
                start_time=0.0,
                end_time=5.0,
                speaker_id=sample_speaker.id,
                word_count=10
            ),
            TranscriptSegment(
                transcript_file_id=transcript_file.id,
                segment_index=1,
                text="Another segment with text.",
                start_time=5.0,
                end_time=8.0,
                speaker_id=sample_speaker.id,
                word_count=5
            )
        ]
        for seg in segments:
            db_session.add(seg)
        db_session.commit()
        for seg in segments:
            db_session.refresh(seg)
        return segments
    
    def test_store_sentences_from_segments(self, service, sample_segments):
        """Test storing sentences from segments."""
        sentences = service.store_sentences_from_segments(sample_segments)
        
        assert len(sentences) > 0
        assert all(s.transcript_segment_id in [seg.id for seg in sample_segments] for s in sentences)
        assert all(s.speaker_id == sample_segments[0].speaker_id for s in sentences)
        assert all(s.timestamp_estimated is True for s in sentences)
        assert all(s.split_method == "punctuation" for s in sentences)
    
    def test_sentence_timestamp_distribution(self, service, sample_segments):
        """Test that timestamps are distributed proportionally."""
        sentences = service.store_sentences_from_segments(sample_segments)
        
        # Check that sentences from first segment have timestamps within segment range
        first_segment_sentences = [s for s in sentences if s.transcript_segment_id == sample_segments[0].id]
        assert len(first_segment_sentences) >= 2  # Should have at least 2 sentences
        
        # Check timestamps are in order
        for i in range(len(first_segment_sentences) - 1):
            assert first_segment_sentences[i].start_time <= first_segment_sentences[i + 1].start_time
            assert first_segment_sentences[i].end_time <= first_segment_sentences[i + 1].end_time
        
        # Check timestamps are within segment bounds
        segment = sample_segments[0]
        for sentence in first_segment_sentences:
            assert sentence.start_time >= segment.start_time
            assert sentence.end_time <= segment.end_time
    
    def test_sentence_word_count(self, service, sample_segments):
        """Test that word counts are calculated correctly."""
        sentences = service.store_sentences_from_segments(sample_segments)
        
        for sentence in sentences:
            assert sentence.word_count > 0
            assert sentence.word_count == len(sentence.text.split())
    
    def test_empty_segment_handling(self, service, db_session, transcript_file, sample_speaker):
        """Test handling of empty segments."""
        empty_segment = TranscriptSegment(
            transcript_file_id=transcript_file.id,
            segment_index=0,
            text="",
            start_time=0.0,
            end_time=0.0,
            speaker_id=sample_speaker.id
        )
        db_session.add(empty_segment)
        db_session.commit()
        db_session.refresh(empty_segment)
        
        sentences = service.store_sentences_from_segments([empty_segment])
        # Empty segment should produce no sentences
        assert len(sentences) == 0
    
    def test_analysis_run_id(self, service, sample_segments):
        """Test storing sentences with analysis_run_id."""
        from uuid import uuid4
        run_id = str(uuid4())
        
        sentences = service.store_sentences_from_segments(sample_segments, analysis_run_id=run_id)
        
        assert all(s.analysis_run_id == run_id for s in sentences)
    
    def test_sentence_indexing(self, service, sample_segments):
        """Test that sentence indices are correct within each segment."""
        sentences = service.store_sentences_from_segments(sample_segments)
        
        # Group by segment
        by_segment = {}
        for sentence in sentences:
            seg_id = sentence.transcript_segment_id
            if seg_id not in by_segment:
                by_segment[seg_id] = []
            by_segment[seg_id].append(sentence)
        
        # Check indices within each segment
        for seg_id, seg_sentences in by_segment.items():
            sorted_sentences = sorted(seg_sentences, key=lambda s: s.sentence_index)
            for i, sentence in enumerate(sorted_sentences):
                assert sentence.sentence_index == i
