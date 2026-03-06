"""
Streamlit implementation of ProgressCallback for workflow execution.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st

from transcriptx.app.progress import ProgressCallback


class StreamlitProgressCallback(ProgressCallback):
    """Maps progress events to Streamlit widgets."""

    def __init__(self, container=None):
        self._container = container or st
        self._status_holder = None
        self._progress_bar = None
        self._log_lines: list[str] = []

    def on_stage_start(self, stage_name: str) -> None:
        self._status_holder = self._container.status(f"**{stage_name}**")
        self._progress_bar = None

    def on_stage_progress(self, message: str, pct: Optional[float] = None) -> None:
        if self._status_holder:
            self._status_holder.update(label=message)
        if pct is not None and self._progress_bar is not None:
            self._progress_bar.progress(pct / 100.0)
        elif pct is not None:
            self._progress_bar = self._container.progress(pct / 100.0)

    def on_stage_complete(self, stage_name: str) -> None:
        if self._status_holder:
            self._status_holder.update(label=f"✓ {stage_name}", state="complete")
            self._status_holder = None

    def on_log(self, message: str, level: str = "info") -> None:
        self._log_lines.append(f"[{level}] {message}")

    def get_log_text(self) -> str:
        return "\n".join(self._log_lines)
