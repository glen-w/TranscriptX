"""
Progress callback protocol for workflow execution.

Progress is best-effort only. Engine correctness must never depend on
progress hooks existing. Workflows call progress.on_* at key boundaries;
if the callback is NullProgress, nothing happens.

Stage names should follow a consistent vocabulary:
- "validating"
- "loading_transcript"
- "running_module:<name>"
- "writing_manifest"
- "complete"
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ProgressCallback(Protocol):
    """Protocol for progress reporting during workflow execution."""

    def on_stage_start(self, stage_name: str) -> None:
        """Called when a stage begins."""
        ...

    def on_stage_progress(self, message: str, pct: Optional[float] = None) -> None:
        """Called with progress within a stage. pct is 0-100 or None."""
        ...

    def on_stage_complete(self, stage_name: str) -> None:
        """Called when a stage completes."""
        ...

    def on_log(self, message: str, level: str = "info") -> None:
        """Called for log messages. level: info, warning, error, debug."""
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
