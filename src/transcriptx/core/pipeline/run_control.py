"""Cooperative cancel/skip signals for a live pipeline run.

Bound via ContextVar so the DAG sequential loop and isolated module waiter
can observe GUI requests without plumbing through every call signature.
``PipelineRunControl`` is thread-safe (``threading.Event``).
"""

from __future__ import annotations

import threading
from contextvars import ContextVar, Token
from dataclasses import dataclass, field

SKIP_REASON_USER = "user_skipped"
SKIP_REASON_CANCELLED = "cancelled"
TERMINATION_CANCELLATION = "cancellation"


@dataclass
class PipelineRunControl:
    """Shared cancel/skip flags for one analysis run."""

    cancel_event: threading.Event = field(default_factory=threading.Event)
    skip_event: threading.Event = field(default_factory=threading.Event)

    def request_cancel(self) -> None:
        self.cancel_event.set()

    def request_skip(self) -> None:
        if not self.cancel_event.is_set():
            self.skip_event.set()

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def consume_skip(self) -> bool:
        """Return True once per skip click (cancel wins if both are set)."""
        if self.cancel_event.is_set():
            return False
        if self.skip_event.is_set():
            self.skip_event.clear()
            return True
        return False


_bound_control: ContextVar[PipelineRunControl | None] = ContextVar(
    "transcriptx_pipeline_run_control", default=None
)


def bind_run_control(control: PipelineRunControl | None) -> Token:
    return _bound_control.set(control)


def reset_run_control(token: Token) -> None:
    _bound_control.reset(token)


def get_bound_run_control() -> PipelineRunControl | None:
    return _bound_control.get()


def pipeline_is_cancelled() -> bool:
    control = _bound_control.get()
    return bool(control is not None and control.is_cancelled())


def pipeline_consume_skip() -> bool:
    control = _bound_control.get()
    return bool(control is not None and control.consume_skip())
