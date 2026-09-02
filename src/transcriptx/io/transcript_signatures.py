"""Filesystem signatures for transcript JSON and speaker-map sidecars."""

from __future__ import annotations

import os
from pathlib import Path


def transcript_summary_signature(path) -> tuple[int, int, int]:
    """(mtime_ns, size, sidecar mtime_ns) for per-path summary cache keys."""
    path_obj = Path(path)
    try:
        file_stat = os.stat(path_obj)
        mtime_ns, size = int(file_stat.st_mtime_ns), int(file_stat.st_size)
    except OSError:
        mtime_ns, size = 0, 0
    sidecar_mtime_ns = 0
    try:
        from transcriptx.io.speaker_map_resolver import speaker_map_sidecar_candidates

        for candidate in speaker_map_sidecar_candidates(path_obj):
            try:
                sidecar_mtime_ns = int(candidate.stat().st_mtime_ns)
                break
            except OSError:
                continue
    except Exception:
        pass
    return mtime_ns, size, sidecar_mtime_ns
