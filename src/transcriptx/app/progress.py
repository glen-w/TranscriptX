"""
Progress callback protocol, structured event schema, and progress snapshot type.

Progress is best-effort only. Engine correctness must never depend on
progress hooks existing. Workflows call progress.on_* at key boundaries;
if the callback is NullProgress, nothing happens.

---------------------------------------------------------------------
Event schema
---------------------------------------------------------------------
Pipeline events are structured dicts with these fields (all optional
except ``event``):

    event        : Literal[EventType] — one of the constants below
    module_name  : str
    index        : int  (1-based position in planned execution order)
    total        : int
    completed    : int
    skipped      : int
    failed       : int
    pct          : float  (0-100; (completed+skipped+failed)/total*100)
    message      : str
    duration_ms  : float
    error        : str

Phase vocabulary (high-level workflow state):
    validating | running_pipeline | finalizing | completed | failed

Event vocabulary (fine-grained occurrences within a phase):
    run_started | module_started | module_completed | module_skipped
    | module_failed | run_completed | run_failed

---------------------------------------------------------------------
Snapshot shape
---------------------------------------------------------------------
The workflow layer maintains a single ``ProgressSnapshot`` in session
state. The UI renders only this object — no state is inferred from logs.

    status          : "running" | "completed" | "failed"
    phase           : one of the phase strings above
    current_module  : last active module (persists after run ends)
    completed       : int
    skipped         : int
    failed          : int
    total           : int
    pct             : float (0-100)
    latest_event    : human-readable description of most recent event
    recent_logs     : list[str] — up to 100 timestamped lines (UI shows last 5-10)
    error           : str | None — terminal failure message

---------------------------------------------------------------------
Log channel
---------------------------------------------------------------------
Logs are timestamped display-only strings. The UI never parses them
to derive state. Use on_log() for human-readable context only.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Literal, Optional, Protocol, TypedDict, runtime_checkable

# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

EventType = Literal[
    "run_started",
    "module_started",
    "module_completed",
    "module_skipped",
    "module_failed",
    "run_completed",
    "run_failed",
]

PhaseType = Literal[
    "validating",
    "running_pipeline",
    "finalizing",
    "completed",
    "failed",
]

StatusType = Literal["running", "completed", "failed"]

# ---------------------------------------------------------------------------
# Structured progress event
# ---------------------------------------------------------------------------

class ProgressEvent(TypedDict, total=False):
    """
    Structured pipeline event dict.  All fields except ``event`` are optional.
    index is 1-based (position in planned execution order).
    pct = (completed + skipped + failed) / total * 100
    """
    event: str          # required — one of EventType
    module_name: str
    index: int          # 1-based
    total: int
    completed: int
    skipped: int
    failed: int
    pct: float
    message: str
    duration_ms: float
    error: str


# ---------------------------------------------------------------------------
# Progress snapshot — the single object the UI renders
# ---------------------------------------------------------------------------

class ProgressSnapshot(TypedDict, total=False):
    """
    Workflow-maintained snapshot stored in st.session_state.
    The UI reads only this dict; no state is inferred from logs.

    recent_logs holds up to 100 timestamped strings; the UI renders the last 5-10.
    current_module persists as the last active module until a new run starts.
    """
    status: str          # StatusType
    phase: str           # PhaseType
    current_module: str
    completed: int
    skipped: int
    failed: int
    total: int
    pct: float
    latest_event: str
    recent_logs: List[str]
    error: Optional[str]


def make_initial_snapshot(total: int) -> ProgressSnapshot:
    """Return a clean snapshot for the start of a new run."""
    return ProgressSnapshot(
        status="running",
        phase="validating",
        current_module="",
        completed=0,
        skipped=0,
        failed=0,
        total=total,
        pct=0.0,
        latest_event="Starting…",
        recent_logs=[],
        error=None,
    )


def _ts() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def update_snapshot_from_event(
    snapshot: ProgressSnapshot,
    event: ProgressEvent,
    log_line: Optional[str] = None,
) -> None:
    """
    Mutate *snapshot* in-place based on a structured pipeline event.
    Optionally append a human-readable log line.

    pct semantics: (completed + skipped + failed) / total * 100 — module
    progress, not time estimate.  Progress may sit flat during long modules,
    then jump; the current_module field provides liveness.
    """
    ev = event.get("event", "")
    total = event.get("total", snapshot.get("total", 0))
    if total:
        snapshot["total"] = total

    if ev == "run_started":
        snapshot["status"] = "running"
        snapshot["phase"] = "running_pipeline"
        snapshot["latest_event"] = event.get("message", "Run started")

    elif ev == "module_started":
        snapshot["phase"] = "running_pipeline"
        snapshot["current_module"] = event.get("module_name", "")
        idx = event.get("index", "")
        tot = event.get("total", "")
        name = event.get("module_name", "")
        snapshot["latest_event"] = (
            f"Starting {name} ({idx}/{tot})" if idx and tot else f"Starting {name}"
        )

    elif ev == "module_completed":
        snapshot["completed"] = event.get("completed", snapshot.get("completed", 0) + 1)
        snapshot["skipped"] = event.get("skipped", snapshot.get("skipped", 0))
        snapshot["failed"] = event.get("failed", snapshot.get("failed", 0))
        _refresh_pct(snapshot)
        name = event.get("module_name", "")
        dur = event.get("duration_ms")
        dur_str = f" ({dur/1000:.1f}s)" if dur is not None else ""
        idx = event.get("index", "")
        tot = event.get("total", "")
        snapshot["latest_event"] = (
            f"Completed {name}{dur_str} ({idx}/{tot})" if idx and tot
            else f"Completed {name}{dur_str}"
        )

    elif ev == "module_skipped":
        snapshot["skipped"] = event.get("skipped", snapshot.get("skipped", 0) + 1)
        snapshot["completed"] = event.get("completed", snapshot.get("completed", 0))
        snapshot["failed"] = event.get("failed", snapshot.get("failed", 0))
        _refresh_pct(snapshot)
        name = event.get("module_name", "")
        reason = event.get("message", "")
        idx = event.get("index", "")
        tot = event.get("total", "")
        reason_str = f": {reason}" if reason else ""
        snapshot["latest_event"] = (
            f"Skipped {name}{reason_str} ({idx}/{tot})" if idx and tot
            else f"Skipped {name}{reason_str}"
        )

    elif ev == "module_failed":
        snapshot["failed"] = event.get("failed", snapshot.get("failed", 0) + 1)
        snapshot["completed"] = event.get("completed", snapshot.get("completed", 0))
        snapshot["skipped"] = event.get("skipped", snapshot.get("skipped", 0))
        _refresh_pct(snapshot)
        name = event.get("module_name", "")
        if name:
            snapshot["current_module"] = name  # persist as last active for forensics
        err = event.get("error", "")
        idx = event.get("index", "")
        tot = event.get("total", "")
        err_str = f": {err}" if err else ""
        snapshot["latest_event"] = (
            f"Failed {name}{err_str} ({idx}/{tot})" if idx and tot
            else f"Failed {name}{err_str}"
        )
        if err:
            snapshot["error"] = err

    elif ev == "run_completed":
        snapshot["status"] = "completed"
        snapshot["phase"] = "completed"
        snapshot["pct"] = 100.0
        snapshot["latest_event"] = event.get("message", "Run completed")

    elif ev == "run_failed":
        snapshot["status"] = "failed"
        snapshot["phase"] = "failed"
        err = event.get("error", "")
        snapshot["latest_event"] = f"Run failed: {err}" if err else "Run failed"
        if err:
            snapshot["error"] = err

    if log_line:
        logs: List[str] = snapshot.get("recent_logs", [])  # type: ignore[assignment]
        logs.append(f"[{_ts()}] {log_line}")
        if len(logs) > 100:
            logs = logs[-100:]
        snapshot["recent_logs"] = logs


def _refresh_pct(snapshot: ProgressSnapshot) -> None:
    """Recompute pct from counts in-place."""
    total = snapshot.get("total", 0)
    if not total:
        return
    done = (
        snapshot.get("completed", 0)
        + snapshot.get("skipped", 0)
        + snapshot.get("failed", 0)
    )
    snapshot["pct"] = min(100.0, done / total * 100.0)


# ---------------------------------------------------------------------------
# ProgressCallback protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class ProgressCallback(Protocol):
    """Protocol for progress reporting during workflow execution."""

    def on_stage_start(self, stage_name: str) -> None:
        """Called when a high-level phase begins."""
        ...

    def on_stage_progress(self, message: str, pct: Optional[float] = None) -> None:
        """Called with progress within a phase. pct is 0-100 or None."""
        ...

    def on_stage_complete(self, stage_name: str) -> None:
        """Called when a high-level phase completes."""
        ...

    def on_log(self, message: str, level: str = "info") -> None:
        """Called for human-readable log lines. level: info, warning, error, debug."""
        ...

    def on_event(self, event: ProgressEvent) -> None:
        """Called with a structured pipeline event. Best-effort; default is no-op."""
        ...


class NullProgress:
    """Default no-op implementation. Progress is best-effort only."""

    def on_stage_start(self, stage_name: str) -> None:
        pass

    def on_stage_progress(self, message: str, pct: Optional[float] = None) -> None:
        pass

    def on_stage_complete(self, stage_name: str) -> None:
        pass

    def on_log(self, message: str, level: str = "info") -> None:
        pass

    def on_event(self, event: ProgressEvent) -> None:
        pass
