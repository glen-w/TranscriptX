"""
Performance logging system for TranscriptX.

Span contract (single source of truth)
--------------------------------------
All performance records are emitted as spans and must follow this shape:

Required fields:
- trace_id: 16 bytes / 32 hex chars
- span_id: 8 bytes / 16 hex chars
- parent_span_id: 8 bytes / 16 hex chars or None
- name: short, stable span name (e.g., "pipeline.run", "module.sentiment.run")
- status_code: "OK" or "ERROR"
- status_message: optional error detail
- start_time, end_time: UTC datetimes
- duration_ms: float milliseconds
- attributes_json: JSON dict of span attributes (OTel-ish)

Optional fields:
- kind: "INTERNAL", "SERVER", "CLIENT"
- events_json: list of events (dicts with name, time, attributes)
- pipeline_run_id, module_run_id, transcript_file_id: nullable FKs

Error handling:
- Exceptions are recorded as events with:
  name="exception"
  attributes: exception.type, exception.message, exception.stacktrace (truncated)

Naming conventions:
- pipeline.run
- module.<name>.run
- transcribe.<engine>
- io.<operation>
"""

import contextvars
import secrets
import threading
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional
from functools import wraps

from transcriptx.core.utils.span_attributes import (
    FILE_NAME,
    SPAN_KIND_INTERNAL,
    STATUS_CODE_ERROR,
    STATUS_CODE_OK,
)

# Global logger instance
_performance_logger: Optional["PerformanceLogger"] = None
_logger_lock = threading.Lock()

_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "trace_id", default=None
)
_span_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "span_id", default=None
)

_STACKTRACE_LIMIT = 4000


def get_session():
    from transcriptx.database import get_session as db_get_session

    return db_get_session()


class PerformanceLogger:
    """
    Singleton logger for performance spans.
    """

    def __init__(self):
        self._write_lock = threading.Lock()

    def start_span(
        self,
        trace_id: str,
        span_id: str,
        name: str,
        start_time: datetime,
        parent_span_id: Optional[str] = None,
        kind: Optional[str] = None,
        attributes_json: Optional[Dict[str, Any]] = None,
        pipeline_run_id: Optional[int] = None,
        module_run_id: Optional[int] = None,
        transcript_file_id: Optional[int] = None,
    ) -> None:
        with self._write_lock:
            from transcriptx.database.repositories import PerformanceSpanRepository

            session = get_session()
            try:
                repo = PerformanceSpanRepository(session)
                repo.start_span(
                    trace_id=trace_id,
                    span_id=span_id,
                    name=name,
                    start_time=start_time,
                    parent_span_id=parent_span_id,
                    kind=kind,
                    attributes_json=attributes_json,
                    pipeline_run_id=pipeline_run_id,
                    module_run_id=module_run_id,
                    transcript_file_id=transcript_file_id,
                )
            finally:
                session.close()

    def end_span_ok(
        self,
        span_id: str,
        end_time: datetime,
        attributes_patch: Optional[Dict[str, Any]] = None,
        events_patch: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        with self._write_lock:
            from transcriptx.database.repositories import PerformanceSpanRepository

            session = get_session()
            try:
                repo = PerformanceSpanRepository(session)
                repo.end_span_ok(
                    span_id=span_id,
                    end_time=end_time,
                    attributes_patch=attributes_patch,
                    events_patch=events_patch,
                )
            finally:
                session.close()

    def end_span_error(
        self,
        span_id: str,
        end_time: datetime,
        exc: Optional[BaseException] = None,
        attributes_patch: Optional[Dict[str, Any]] = None,
        events_patch: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        with self._write_lock:
            from transcriptx.database.repositories import PerformanceSpanRepository

            session = get_session()
            try:
                repo = PerformanceSpanRepository(session)
                repo.end_span_error(
                    span_id=span_id,
                    end_time=end_time,
                    exc=exc,
                    attributes_patch=attributes_patch,
                    events_patch=events_patch,
                )
            finally:
                session.close()

    def update_span_attributes(
        self,
        span_id: str,
        attributes_patch: Dict[str, Any],
    ) -> None:
        """
        Update span attributes while the span is still active.
        This allows metadata to be persisted immediately rather than waiting for span completion.

        Args:
            span_id: The span ID to update
            attributes_patch: Dictionary of attributes to merge into existing attributes
        """
        with self._write_lock:
            from transcriptx.database.repositories import PerformanceSpanRepository

            session = get_session()
            try:
                repo = PerformanceSpanRepository(session)
                repo.update_span_attributes(
                    span_id=span_id,
                    attributes_patch=attributes_patch,
                )
            finally:
                session.close()


def _generate_trace_id() -> str:
    return secrets.token_hex(16)


def _generate_span_id() -> str:
    return secrets.token_hex(8)


def _truncate_stacktrace(stacktrace: str) -> str:
    if len(stacktrace) <= _STACKTRACE_LIMIT:
        return stacktrace
    return stacktrace[:_STACKTRACE_LIMIT] + "..."


def get_current_trace_id() -> Optional[str]:
    return _trace_id_var.get()


def get_current_span_id() -> Optional[str]:
    return _span_id_var.get()


class TraceContext:
    """Context manager for setting trace/span IDs (thread/task-local)."""

    def __init__(self, trace_id: Optional[str] = None, span_id: Optional[str] = None):
        self.trace_id = trace_id
        self.span_id = span_id
        self._trace_token: Optional[contextvars.Token] = None
        self._span_token: Optional[contextvars.Token] = None

    def __enter__(self):
        if self.trace_id is not None:
            self._trace_token = _trace_id_var.set(self.trace_id)
        if self.span_id is not None:
            self._span_token = _span_id_var.set(self.span_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._span_token is not None:
            _span_id_var.reset(self._span_token)
        if self._trace_token is not None:
            _trace_id_var.reset(self._trace_token)


def with_span(
    name: str,
    attrs: Optional[Dict[str, Any]] = None,
    kind: Optional[str] = None,
    file_name: str = "unknown",
) -> "TimedJob":
    job = TimedJob(name, file_name, kind=kind)
    if attrs:
        job.add_metadata(attrs)
    return job


class TimedJob:
    """
    Context manager for timing job execution.

    Usage:
        with TimedJob("transcribe.whisperx", "audio.mp3") as job:
            # ... do work ...
            job.add_metadata({"model": "large-v2"})
    """

    def __init__(
        self,
        job_type: str,
        file_name: str,
        logger_instance: Optional[PerformanceLogger] = None,
        kind: Optional[str] = None,
        pipeline_run_id: Optional[int] = None,
        module_run_id: Optional[int] = None,
        transcript_file_id: Optional[int] = None,
    ):
        """
        Initialize a timed job.

        Args:
            job_type: Type of job
            file_name: Name of file being processed
            logger_instance: Optional logger instance (uses global if not provided)
        """
        self.job_type = job_type
        self.file_name = file_name
        self.kind = kind or SPAN_KIND_INTERNAL
        self.logger = logger_instance or get_performance_logger()
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.metadata: Dict[str, Any] = {FILE_NAME: file_name}
        self.status = STATUS_CODE_OK
        self.pipeline_run_id = pipeline_run_id
        self.module_run_id = module_run_id
        self.transcript_file_id = transcript_file_id
        self.span_id: Optional[str] = None
        self.trace_id: Optional[str] = None
        self.parent_span_id: Optional[str] = None
        self._trace_token: Optional[contextvars.Token] = None
        self._span_token: Optional[contextvars.Token] = None

    def __enter__(self):
        """Start timing."""
        self.start_time = datetime.utcnow()
        current_trace = get_current_trace_id()
        if current_trace is None:
            self.trace_id = _generate_trace_id()
            self._trace_token = _trace_id_var.set(self.trace_id)
        else:
            self.trace_id = current_trace
        self.parent_span_id = get_current_span_id()
        self.span_id = _generate_span_id()
        self._span_token = _span_id_var.set(self.span_id)

        self.logger.start_span(
            trace_id=self.trace_id,
            span_id=self.span_id,
            name=self.job_type,
            start_time=self.start_time,
            parent_span_id=self.parent_span_id,
            kind=self.kind,
            attributes_json=self.metadata.copy(),
            pipeline_run_id=self.pipeline_run_id,
            module_run_id=self.module_run_id,
            transcript_file_id=self.transcript_file_id,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop timing and log the job."""
        self.end_time = datetime.utcnow()
        exception_event = None

        if exc_type is not None:
            self.status = STATUS_CODE_ERROR
            stacktrace = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
            exception_event = {
                "name": "exception",
                "time": self.end_time.isoformat(),
                "attributes": {
                    "exception.type": exc_type.__name__,
                    "exception.message": str(exc_val) if exc_val else "",
                    "exception.stacktrace": _truncate_stacktrace(stacktrace),
                },
            }

        if self.start_time and self.end_time and self.span_id:
            if self.status == STATUS_CODE_OK:
                self.logger.end_span_ok(
                    span_id=self.span_id,
                    end_time=self.end_time,
                    attributes_patch=self.metadata.copy(),
                    events_patch=[exception_event] if exception_event else None,
                )
            else:
                self.logger.end_span_error(
                    span_id=self.span_id,
                    end_time=self.end_time,
                    exc=exc_val,
                    attributes_patch=self.metadata.copy(),
                    events_patch=[exception_event] if exception_event else None,
                )

        if self._span_token is not None:
            _span_id_var.reset(self._span_token)
        if self._trace_token is not None:
            _trace_id_var.reset(self._trace_token)

        return False  # Don't suppress exceptions

    def add_metadata(self, metadata: Dict[str, Any]) -> None:
        """
        Add metadata to the job log entry and persist immediately to database.

        This ensures metadata is preserved even if the process is interrupted
        before the span completes.
        """
        # Update in-memory metadata dict (used when span ends)
        self.metadata.update(metadata)

        # Persist immediately to database if span has been started
        if self.span_id:
            try:
                self.logger.update_span_attributes(
                    span_id=self.span_id,
                    attributes_patch=metadata,
                )
            except Exception:
                # Don't fail the main operation if metadata update fails
                # The metadata is still in self.metadata and will be persisted on span completion
                pass


def timed_job(job_type: str):
    """
    Decorator to automatically time a function execution.

    Usage:
        @timed_job("audio.convert.wav_to_mp3")
        def convert_wav_to_mp3(wav_path, output_dir):
            # ... conversion logic ...
            pass
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Try to extract file name from arguments
            file_name = "unknown"
            if args:
                first_arg = args[0]
                if isinstance(first_arg, (str, Path)):
                    file_name = Path(first_arg).name
                elif hasattr(first_arg, "name"):
                    file_name = first_arg.name

            with TimedJob(job_type, file_name) as job:
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    job.status = "failed"
                    job.metadata["error"] = str(e)
                    raise

        return wrapper

    return decorator


def get_performance_logger() -> PerformanceLogger:
    """Get the global performance logger instance (singleton)."""
    global _performance_logger

    with _logger_lock:
        if _performance_logger is None:
            _performance_logger = PerformanceLogger()
        return _performance_logger
