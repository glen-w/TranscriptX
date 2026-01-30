"""
Tests for SpeakerIdentityService.

This module tests the speaker identity resolution service.
"""

import pytest
from transcriptx.database.speaker_profiling import SpeakerIdentityService
from transcriptx.database.models import Speaker, TranscriptFile, SpeakerResolutionEvent


class TestSpeakerIdentityService:
    """Tests for SpeakerIdentityService."""
    
    @pytest.fixture
    def service(self, db_session):
        """Fixture for SpeakerIdentityService."""
        with pytest.MonkeyPatch().context() as m:
            from transcriptx.database import speaker_profiling
            m.setattr(speaker_profiling, 'get_session', lambda: db_session)
            # Also patch the services it uses
            from transcriptx.database import vocabulary_storage, cross_session_tracking
            m.setattr(vocabulary_storage, 'get_session', lambda: db_session)
            m.setattr(cross_session_tracking, 'get_session', lambda: db_session)
            
            service = SpeakerIdentityService()
            service.session = db_session
            # Patch the sub-services to use our session
            service.vocabulary_service.session = db_session
            yield service
            service.close()
    
    @pytest.fixture
    def transcript_file(self, db_session):
        """Create a test transcript file."""
        tf = TranscriptFile(
            file_path="/test/path/transcript.json",
            file_name="transcript.json"
        )
        db_session.add(tf)
        db_session.commit()
        db_session.refresh(tf)
        return tf
    
    def test_resolve_speaker_identity_new_speaker(self, service, transcript_file):
        """Test resolving identity for a new speaker."""
        session_data = [
            {"text": "Hello, this is a test.", "start": 0.0, "end": 3.0}
        ]
        
        speaker, is_new, metadata = service.resolve_speaker_identity(
            diarized_label="SPEAKER_01",
            transcript_file_id=transcript_file.id,
            session_data=session_data
        )
        
        assert speaker is not None
        assert is_new is True
        assert metadata["method"] == "new_speaker"
        assert metadata["confidence"] == 1.0
    
    def test_resolve_speaker_identity_canonical_id(self, service, transcript_file, db_session):
        """Test resolving identity via canonical_id."""
        # Create speaker with canonical_id
        speaker = Speaker(
            name="Alice",
            display_name="Alice",
            canonical_id="alice",
            confidence_score=1.0
        )
        db_session.add(speaker)
        db_session.commit()
        db_session.refresh(speaker)
        
        session_data = [{"text": "Test text.", "start": 0.0, "end": 2.0}]
        
        resolved_speaker, is_new, metadata = service.resolve_speaker_identity(
            diarized_label="Alice",
            transcript_file_id=transcript_file.id,
            session_data=session_data
        )
        
        assert resolved_speaker.id == speaker.id
        assert is_new is False
        assert metadata["method"] == "canonical_id"
        assert metadata["confidence"] == 1.0
    
    def test_resolve_speaker_identity_logs_event(self, service, transcript_file, db_session):
        """Test that resolution events are logged."""
        session_data = [{"text": "Test text.", "start": 0.0, "end": 2.0}]
        
        speaker, is_new, metadata = service.resolve_speaker_identity(
            diarized_label="SPEAKER_01",
            transcript_file_id=transcript_file.id,
            session_data=session_data
        )
        
        # Check that event was logged
        events = db_session.query(SpeakerResolutionEvent).filter_by(
            transcript_file_id=transcript_file.id,
            diarized_label="SPEAKER_01"
        ).all()
        
        assert len(events) == 1
        event = events[0]
        assert event.speaker_id == speaker.id
        assert event.method == metadata["method"]
        assert event.confidence == metadata["confidence"]
        assert event.evidence_json == metadata["evidence"]
    
    def test_resolve_speaker_identity_analysis_run_id(self, service, transcript_file):
        """Test resolution with analysis_run_id."""
        from uuid import uuid4
        run_id = str(uuid4())
        
        session_data = [{"text": "Test text.", "start": 0.0, "end": 2.0}]
        
        speaker, is_new, metadata = service.resolve_speaker_identity(
            diarized_label="SPEAKER_01",
            transcript_file_id=transcript_file.id,
            session_data=session_data,
            analysis_run_id=run_id
        )
        
        # Check event has analysis_run_id
        events = service.session.query(SpeakerResolutionEvent).filter_by(
            transcript_file_id=transcript_file.id
        ).all()
        
        assert len(events) == 1
        assert events[0].analysis_run_id == run_id
    
    def test_update_speaker_canonical_id(self, service, sample_speaker):
        """Test updating speaker canonical_id."""
        service.update_speaker_canonical_id(
            speaker_id=sample_speaker.id,
            canonical_id="test_canonical",
            confidence_score=0.9
        )
        
        service.session.refresh(sample_speaker)
        assert sample_speaker.canonical_id == "test_canonical"
        assert sample_speaker.confidence_score == 0.9
    
    def test_resolution_metadata_structure(self, service, transcript_file):
        """Test that resolution metadata has correct structure."""
        session_data = [{"text": "Test text.", "start": 0.0, "end": 2.0}]
        
        speaker, is_new, metadata = service.resolve_speaker_identity(
            diarized_label="SPEAKER_01",
            transcript_file_id=transcript_file.id,
            session_data=session_data
        )
        
        assert "method" in metadata
        assert "confidence" in metadata
        assert "evidence" in metadata
        assert "timestamp" in metadata
        assert isinstance(metadata["confidence"], float)
        assert 0.0 <= metadata["confidence"] <= 1.0
