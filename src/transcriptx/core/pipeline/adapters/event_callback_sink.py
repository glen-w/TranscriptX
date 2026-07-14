"""Callback-based event sink adapter for pipeline runs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from transcriptx.core.pipeline.ports import EventSink


class EventCallbackSink(EventSink):
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
        if self._on_event is None:
            return
        try:
            self._on_event(event)
        except Exception:
            # Best effort by contract.
            pass
