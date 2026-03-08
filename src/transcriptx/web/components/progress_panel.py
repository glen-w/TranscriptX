"""
Streamlit progress panel — pure renderer of a ProgressSnapshot dict.

The panel reads exactly one object (the snapshot) from session state and
renders five things:
  1. Overall status line  (from snapshot["phase"])
  2. Current module       (from snapshot["current_module"])
  3. Progress bar         (from snapshot["pct"] + counts)
  4. Latest event line    (from snapshot["latest_event"])
  5. Last 5-10 log lines  (tail of snapshot["recent_logs"])

No state is inferred from logs. No state is stored inside this class.
StreamlitProgressCallback bridges the ProgressCallback protocol and
on_event to the snapshot stored in st.session_state.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, MutableMapping, Optional

import streamlit as st

from transcriptx.app.progress import (
    NullProgress,
    ProgressCallback,
    ProgressEvent,
    ProgressSnapshot,
    update_snapshot_from_event,
)

# Session-state key under which the running snapshot is stored
SNAPSHOT_KEY = "run_progress_snapshot"
# Number of log lines to render in the panel
PANEL_LOG_LINES = 8


# ---------------------------------------------------------------------------
# Pure rendering function
# ---------------------------------------------------------------------------

def render_progress_panel(snapshot: ProgressSnapshot) -> None:
    """
    Render the compact five-item progress panel from a snapshot dict.
    This function is stateless and has no side effects beyond Streamlit widgets.
    """
    phase: str = snapshot.get("phase", "running")  # type: ignore[assignment]
    status: str = snapshot.get("status", "running")  # type: ignore[assignment]
    current_module: str = snapshot.get("current_module", "")  # type: ignore[assignment]
    completed: int = snapshot.get("completed", 0)  # type: ignore[assignment]
    skipped: int = snapshot.get("skipped", 0)  # type: ignore[assignment]
    failed: int = snapshot.get("failed", 0)  # type: ignore[assignment]
    total: int = snapshot.get("total", 0)  # type: ignore[assignment]
    pct: float = snapshot.get("pct", 0.0)  # type: ignore[assignment]
    latest_event: str = snapshot.get("latest_event", "")  # type: ignore[assignment]
    recent_logs: list = snapshot.get("recent_logs", [])  # type: ignore[assignment]
    error: Optional[str] = snapshot.get("error")  # type: ignore[assignment]

    done = completed + skipped + failed

    # 1. Overall status line
    phase_labels: Dict[str, str] = {
        "validating": "Validating…",
        "running_pipeline": "Running pipeline…",
        "finalizing": "Finalizing…",
        "completed": "Completed",
        "failed": "Failed",
    }
    phase_label = phase_labels.get(phase, phase.replace("_", " ").title())
    if status == "completed":
        st.success(f"**{phase_label}**")
    elif status == "failed":
        st.error(f"**{phase_label}**")
        if error:
            st.error(error)
    else:
        st.info(f"**{phase_label}**")

    # 2. Current module
    if current_module:
        prefix = "Last module:" if status in ("completed", "failed") else "Current module:"
        st.markdown(f"{prefix} `{current_module}`")

    # 3. Progress bar with x / y modules
    #    Label explains it is module progress, not time progress
    if total > 0:
        bar_label = f"{done} / {total} modules"
        if skipped:
            bar_label += f"  ·  {skipped} skipped"
        if failed:
            bar_label += f"  ·  {failed} failed"
        st.progress(min(pct / 100.0, 1.0), text=bar_label)
    else:
        st.progress(0.0)

    # 4. Latest event line
    if latest_event:
        st.caption(latest_event)

    # 5. Last N log lines
    if recent_logs:
        tail = recent_logs[-PANEL_LOG_LINES:]
        with st.expander("Recent logs", expanded=False):
            st.text("\n".join(tail))


# ---------------------------------------------------------------------------
# StreamlitProgressCallback — bridges ProgressCallback + on_event to snapshot
# ---------------------------------------------------------------------------

class StreamlitProgressCallback:
    """
    Implements ProgressCallback protocol and bridges pipeline events into the
    shared ProgressSnapshot stored in st.session_state[SNAPSHOT_KEY].

    The snapshot must be initialised in session state before the run starts
    (done by run_analysis.py). This class only mutates it; it never creates it.
    """

    def __init__(self) -> None:
        pass

    def _snap(self) -> Optional[MutableMapping[str, Any]]:
        return st.session_state.get(SNAPSHOT_KEY)

    # ------------------------------------------------------------------
    # ProgressCallback protocol
    # ------------------------------------------------------------------

    def on_stage_start(self, stage_name: str) -> None:
        snap = self._snap()
        if snap is not None:
            snap["phase"] = stage_name
            snap["latest_event"] = stage_name.replace("_", " ").title() + "…"

    def on_stage_progress(self, message: str, pct: Optional[float] = None) -> None:
        snap = self._snap()
        if snap is not None:
            snap["latest_event"] = message
            if pct is not None:
                snap["pct"] = min(100.0, float(pct))

    def on_stage_complete(self, stage_name: str) -> None:
        pass  # run-level completion is handled via on_event

    def on_log(self, message: str, level: str = "info") -> None:
        """Append a timestamped log line to recent_logs. Never infer state from it."""
        snap = self._snap()
        if snap is None:
            return
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        logs: list = snap.get("recent_logs", [])
        logs.append(f"[{ts}] {message}")
        if len(logs) > 100:
            logs = logs[-100:]
        snap["recent_logs"] = logs

    def on_event(self, event: ProgressEvent) -> None:
        """Update the snapshot from a structured pipeline event."""
        snap = self._snap()
        if snap is not None:
            update_snapshot_from_event(snap, event)  # type: ignore[arg-type]

    def get_log_text(self) -> str:
        """Return all recent logs as a single string (for legacy callers)."""
        snap = self._snap()
        if snap is None:
            return ""
        return "\n".join(snap.get("recent_logs", []))
