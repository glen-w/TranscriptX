"""Prompt-free workflow orchestration. No terminal I/O, no UI imports."""

from transcriptx.app.workflows.analysis import run_analysis, validate_analysis_readiness
from transcriptx.app.workflows.speaker import identify_speakers

__all__ = [
    "run_analysis",
    "validate_analysis_readiness",
    "identify_speakers",
]
