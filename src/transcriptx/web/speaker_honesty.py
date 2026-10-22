"""Shared T0/T1 speaker-honesty copy for Overview, Charts, and Import."""

from __future__ import annotations

from pathlib import Path
from typing import Any

T0_NO_NAMED_SPEAKERS_BANNER = (
    "No named speakers — content-oriented analysis only. Name speakers in "
    "Speaker Identification, enable **Allow analysis without named speakers** "
    "on Run Analysis, treat as a single speaker, or re-transcribe with "
    "diarization to unlock interaction charts."
)

T1_IMPORT_PLACEHOLDER_CAPTION = (
    "Imported as placeholder speaker labels (SPEAKER_00). On Run Analysis, "
    "check **Treat as single speaker** if this is a monologue, or name speakers "
    "in Speaker Identification before a Balanced run."
)


def should_show_t0_named_speaker_banner(named_count: int | None) -> bool:
    return named_count is not None and named_count == 0


def render_t0_named_speaker_banner(st_mod: Any, named_count: int | None) -> bool:
    """Render the T0 info banner. Return True when shown."""
    if not should_show_t0_named_speaker_banner(named_count):
        return False
    st_mod.info(T0_NO_NAMED_SPEAKERS_BANNER)
    return True


def should_show_t1_import_caption(transcript_path: Path) -> bool:
    """True when the admitted transcript has no human-named speakers."""
    try:
        from transcriptx.core.utils.speaker_extraction import (
            named_speaker_count_for_path,
        )

        return named_speaker_count_for_path(transcript_path) == 0
    except Exception:
        return False


def render_t1_import_caption(st_mod: Any, transcript_path: Path) -> bool:
    """Render the T1 import hint. Return True when shown."""
    if not should_show_t1_import_caption(transcript_path):
        return False
    st_mod.caption(T1_IMPORT_PLACEHOLDER_CAPTION)
    return True
