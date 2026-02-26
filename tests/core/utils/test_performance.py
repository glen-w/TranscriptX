"""
Tests for performance logging and estimation.

This module tests span-based performance logging and performance estimation.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from transcriptx.core.utils.performance_logger import get_performance_logger, TimedJob
from transcriptx.core.utils.performance_estimator import PerformanceEstimator
from transcriptx.database.models import Base, PerformanceSpan
from transcriptx.database.repositories import PerformanceSpanRepository


@pytest.fixture
def db_session_factory():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal


class TestPerformanceLogger:
    """Tests for PerformanceLogger class."""

    def test_logs_span_execution(self, db_session_factory):
        """Test that TimedJob writes a span record."""

        def _session():
            return db_session_factory()

        with patch(
            "transcriptx.core.utils.performance_logger.get_session",
            side_effect=_session,
        ):
            with TimedJob("test_job", "test.wav") as job:
                job.add_metadata({"model": "tiny"})

        session = db_session_factory()
        try:
            spans = session.query(PerformanceSpan).all()
            assert len(spans) == 1
            span = spans[0]
            assert span.name == "test_job"
            assert span.status_code == "OK"
            assert span.attributes_json.get("model") == "tiny"
            assert span.attributes_json.get("file.name") == "test.wav"
        finally:
            session.close()

    def test_logs_exception_event(self, db_session_factory):
        """Test that exceptions are recorded as span events."""

        def _session():
            return db_session_factory()

        with patch(
            "transcriptx.core.utils.performance_logger.get_session",
            side_effect=_session,
        ):
            with pytest.raises(ValueError):
                with TimedJob("test_job", "test.wav"):
                    raise ValueError("boom")

        session = db_session_factory()
        try:
            span = session.query(PerformanceSpan).first()
            assert span.status_code == "ERROR"
            assert span.events_json
            assert span.events_json[0]["name"] == "exception"
        finally:
            session.close()


class TestGetPerformanceLogger:
    """Tests for get_performance_logger function."""

    def test_returns_singleton_instance(self):
        """Test that get_performance_logger returns singleton."""
        logger1 = get_performance_logger()
        logger2 = get_performance_logger()
        assert logger1 is logger2


class TestPerformanceEstimator:
    """Tests for performance estimator with spans."""

    def test_estimate_conversion_uses_spans(self, db_session_factory):
        """Estimator should use spans and compute a numeric estimate."""
        session = db_session_factory()
        try:
            repo = PerformanceSpanRepository(session)
            start_time = datetime.utcnow()
            span_id = "abcd1234abcd1234"
            repo.start_span(
                trace_id="trace1234trace1234trace1234trace1234",
                span_id=span_id,
                name="audio.convert.wav_to_mp3",
                start_time=start_time,
                attributes_json={"input_file_size_mb": 10.0, "bitrate": "192k"},
            )
            repo.end_span_ok(
                span_id=span_id,
                end_time=start_time + timedelta(seconds=5),
            )
        finally:
            session.close()

        def _session():
            return db_session_factory()

        with patch(
            "transcriptx.core.utils.performance_estimator.get_session",
            side_effect=_session,
        ):
            estimator = PerformanceEstimator()
            estimate = estimator.estimate_conversion_time(
                file_size_mb=10.0, bitrate="192k"
            )
            assert estimate["estimated_seconds"] is not None
