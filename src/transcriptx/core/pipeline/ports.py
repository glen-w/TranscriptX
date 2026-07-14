"""Port interfaces for pipeline sinks and persistence stores."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from transcriptx.core.pipeline.contracts import ExecutionPlan, PersistenceOutcome


class EventSink(Protocol):
    def emit(self, event: Dict[str, Any]) -> None: ...


class ReporterSink(Protocol):
    def info(self, message: str) -> None: ...

    def warning(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...


class ExecutionPlanStore(Protocol):
    def save(self, plan: ExecutionPlan, output_dir: str) -> PersistenceOutcome: ...


class RunStateStore(Protocol):
    def update(self, pipeline_results: Dict[str, Any]) -> PersistenceOutcome: ...


class ArtifactStore(Protocol):
    def save_manifest(
        self, payload: Dict[str, Any], output_dir: str
    ) -> PersistenceOutcome: ...

    def index_artifacts(self, output_dir: str) -> List[Dict[str, str]]: ...


class ConfigSnapshotStore(Protocol):
    def save(self, output_dir: str, payload: Dict[str, Any]) -> PersistenceOutcome: ...


class RunReportStore(Protocol):
    def save(self, output_dir: str, run_report: Any) -> PersistenceOutcome: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    def new_suffix(self) -> str: ...


@dataclass
class SystemClock:
    def now(self) -> datetime:
        return datetime.utcnow()


@dataclass
class Uuid4IdGenerator:
    def new_suffix(self) -> str:
        import uuid

        return uuid.uuid4().hex[:8]


class NullEventSink:
    def emit(self, event: Dict[str, Any]) -> None:
        return


class CallbackEventSink:
    def __init__(
        self,
        *,
        on_event: Optional[Any] = None,
        event_collector: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self._on_event = on_event
        self._event_collector = event_collector

    def emit(self, event: Dict[str, Any]) -> None:
        if self._event_collector is not None:
            self._event_collector.append(event)
        if self._on_event is not None:
            try:
                self._on_event(event)
            except Exception:
                # Contract: event callback errors never corrupt run outcome.
                pass
