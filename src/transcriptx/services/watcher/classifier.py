"""Classify watched paths as transcript, audio, or ignore."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from transcriptx.services.watcher.settings import DirectoryWatcherSettings


class WatchKind(str, Enum):
    TRANSCRIPT = "transcript"
    AUDIO = "audio"
    IGNORE = "ignore"


def classify_path(path: Path | str, settings: DirectoryWatcherSettings) -> WatchKind:
    ext = Path(path).suffix.lower()
    if ext in set(settings.extensions_transcript):
        return WatchKind.TRANSCRIPT
    if ext in set(settings.extensions_audio):
        return WatchKind.AUDIO
    return WatchKind.IGNORE
