"""
Database fixtures for TranscriptX testing.

This module provides comprehensive database fixtures for testing database operations,
models, and integrations. All fixtures use isolated test databases to ensure test
independence and prevent data pollution.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator, Optional
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession, sessionmaker

from transcriptx.database.models import (
    Base,
    Speaker,
    SpeakerProfile,
    Conversation,
    AnalysisResult,
    Session,
    BehavioralFingerprint,
    TranscriptFile,
    TranscriptSegment,
    TranscriptSentence,
    SpeakerVocabularyWord,
    SpeakerResolutionEvent,
)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """
    Create a temporary database URL for testing.
    
    Returns:
        SQLite database URL pointing to a temporary file
        
    Note:
        The database file is created in a temporary directory and will be
        cleaned up after all tests complete.
    """
    temp_dir = tempfile.mkdtemp(prefix="transcriptx_test_")
    db_path = Path(temp_dir) / "test_transcriptx.db"
    return f"sqlite:///{db_path}"


@pytest.fixture(scope="session")
def test_database_engine(test_database_url: str):
    """
    Create a test database engine.
    
    Args:
        test_database_url: Database URL for test database
        
    Yields:
        SQLAlchemy engine instance
        
    Note:
        Creates all tables before tests and drops them after.
    """
    engine = create_engine(
        test_database_url,
        connect_args={"check_same_thread": False},
        poolclass=None,  # Use default pool
        echo=False  # Set to True for SQL debugging
    )
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Cleanup: drop all tables
    Base.metadata.drop_all(engine)
    engine.dispose()
    
    # Remove database directory (handles WAL/shm files)
    db_path = Path(test_database_url.replace("sqlite:///", ""))
    if db_path.parent.exists():
        shutil.rmtree(db_path.parent, ignore_errors=True)


@pytest.fixture
def db_session(test_database_engine) -> Generator[DBSession, None, None]:
    """
    Create a database session for testing.
    
    Args:
        test_database_engine: Test database engine
        
    Yields:
        SQLAlchemy session instance
        
    Note:
        Automatically rolls back all changes after each test to ensure
        test isolation. Each test gets a fresh database state.
    """
    connection = test_database_engine.connect()
    transaction = connection.begin()
    
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    
    yield session
    
    # Rollback all changes
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_speaker(db_session: DBSession) -> Speaker:
    """
    Create a sample speaker for testing.
    
    Args:
        db_session: Database session
        
    Returns:
        Speaker instance with test data
    """
    speaker = Speaker(
        name="Test Speaker",
        display_name="Test Display Name",
        email="test@example.com",
        organization="Test Org",
        role="Test Role"
    )
    db_session.add(speaker)
    db_session.commit()
    db_session.refresh(speaker)
    return speaker


@pytest.fixture
def sample_speaker_profile(db_session: DBSession, sample_speaker: Speaker) -> SpeakerProfile:
    """
    Create a sample speaker profile for testing.
    
    Args:
        db_session: Database session
        sample_speaker: Speaker instance
        
    Returns:
        SpeakerProfile instance with test data
    """
    profile = SpeakerProfile(
        speaker_id=sample_speaker.id,
        conversation_id="test_conversation_1",
        behavioral_data={
            "avg_sentiment": 0.5,
            "avg_emotion": "neutral",
            "speaking_rate": 150.0,
            "interruption_rate": 0.1
        },
        confidence_score=0.85
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


@pytest.fixture
def sample_conversation(db_session: DBSession) -> Conversation:
    """
    Create a sample conversation for testing.
    
    Args:
        db_session: Database session
        
    Returns:
        Conversation instance with test data
    """
    conversation = Conversation(
        conversation_id="test_conversation_1",
        transcript_path="/test/path/transcript.json",
        metadata={"duration": 3600.0, "language": "en"}
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation


@pytest.fixture
def sample_analysis_result(db_session: DBSession, sample_conversation: Conversation) -> AnalysisResult:
    """
    Create a sample analysis result for testing.
    
    Args:
        db_session: Database session
        sample_conversation: Conversation instance
        
    Returns:
        AnalysisResult instance with test data
    """
    result = AnalysisResult(
        conversation_id=sample_conversation.conversation_id,
        module_name="sentiment",
        result_data={"overall_sentiment": "positive", "score": 0.7},
        status="completed"
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(result)
    return result


@pytest.fixture
def multiple_speakers(db_session: DBSession) -> list[Speaker]:
    """
    Create multiple speakers for testing.
    
    Args:
        db_session: Database session
        
    Returns:
        List of Speaker instances
    """
    speakers = []
    for i in range(5):
        speaker = Speaker(
            name=f"Speaker {i}",
            display_name=f"Display Name {i}",
            email=f"speaker{i}@example.com"
        )
        db_session.add(speaker)
        speakers.append(speaker)
    
    db_session.commit()
    for speaker in speakers:
        db_session.refresh(speaker)
    
    return speakers


@pytest.fixture
def mock_database_manager():
    """
    Mock database manager for testing without actual database.
    
    Yields:
        Mock DatabaseManager instance
    """
    with patch('transcriptx.database.database.DatabaseManager') as mock_manager:
        mock_instance = MagicMock()
        mock_manager.return_value = mock_instance
        
        # Mock common methods
        mock_instance.get_session.return_value = MagicMock()
        mock_instance.init_database.return_value = True
        mock_instance.close.return_value = None
        
        yield mock_instance


@pytest.fixture
def isolated_database(tmp_path: Path) -> Generator[str, None, None]:
    """
    Create an isolated database in a temporary directory.
    
    Args:
        tmp_path: Temporary directory path
        
    Yields:
        Database URL string
        
    Note:
        Database is automatically cleaned up after test completes.
    """
    db_path = tmp_path / "isolated_test.db"
    db_url = f"sqlite:///{db_path}"
    
    # Create engine and tables
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    
    yield db_url
    
    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()
    if db_path.exists():
        db_path.unlink()

