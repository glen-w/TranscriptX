"""
Shared transcript option formatting for dropdowns across web pages.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from transcriptx.core.utils.analysis_picker_status import format_with_analysis_status
from transcriptx.web.corpus_inventory_display import format_speaker_id_label

_SPEAKER_ID_STATUS_UNKNOWN = "Unknown"


def decorate_transcript_picker_label(
    name: str,
    *,
    path: str | Path | None = None,
    slug: str | None = None,
) -> str:
    """Append ``(no analysis|partial analysis|analysis complete)`` to a picker name."""
    from transcriptx.web.cache_helpers import get_cached_analysis_picker_status

    status = get_cached_analysis_picker_status().status_for(path=path, slug=slug)
    return format_with_analysis_status(name, status)


def format_transcript_option_with_analysis_status(name: str, status: str) -> str:
    """Render ``Name (status)`` for transcript pickers."""
    return format_with_analysis_status(name, status)


def format_transcript_option_with_speaker_id_status(
    name: str, status_label: str
) -> str:
    """Render ``Name (Complete|Partial|Not started|Unknown)`` for Speaker ID pickers."""
    return format_with_analysis_status(name, status_label)


def decorate_transcript_picker_label_with_speaker_id(
    name: str,
    *,
    path: str | Path | None = None,
    status_label: str | None = None,
) -> str:
    """Append speaker-identification status in brackets to a picker name."""
    if status_label is None:
        looked_up = speaker_id_status_labels_for_paths(
            [path] if path is not None else []
        )
        status_label = looked_up.get(
            str(path) if path is not None else "",
            _SPEAKER_ID_STATUS_UNKNOWN,
        )
    return format_transcript_option_with_speaker_id_status(name, status_label)


def speaker_id_status_labels_for_paths(
    paths: Iterable[str | Path | None],
) -> dict[str, str]:
    """Map picker paths to Library speaker-ID status labels (one inventory read)."""
    from transcriptx.web.cache_helpers import get_cached_corpus_inventory
    from transcriptx.web.services.transcript_context_resolver import (
        paths_match,
        tolerant_resolve,
    )

    wanted = [p for p in paths if p is not None]
    if not wanted:
        return {}
    rows = get_cached_corpus_inventory()
    by_resolved: dict[str, str] = {}
    for row in rows:
        speaker = getattr(row, "speaker", None)
        transcript_path = getattr(row, "transcript_path", None)
        if speaker is None or transcript_path is None:
            continue
        by_resolved[tolerant_resolve(transcript_path)] = format_speaker_id_label(
            speaker
        )

    labels: dict[str, str] = {}
    for path in wanted:
        key = str(path)
        resolved = tolerant_resolve(path)
        label = by_resolved.get(resolved)
        if label is None:
            for row in rows:
                row_path = getattr(row, "transcript_path", None)
                if row_path is None:
                    continue
                if paths_match(row_path, path):
                    label = format_speaker_id_label(row.speaker)
                    break
        labels[key] = label or _SPEAKER_ID_STATUS_UNKNOWN
    return labels


def format_transcript_option_with_speaker_status(summary: Any) -> str:
    """
    Format a transcript summary label with speaker-identification status.

    Expected attrs on ``summary``:
    - base_name
    - speaker_map_status
    - segment_count
    - unidentified_speaker_count
    - ignored_speaker_count
    """
    base_name = str(getattr(summary, "base_name", "") or "")
    status = str(getattr(summary, "speaker_map_status", "none") or "none")
    seg_count = int(getattr(summary, "segment_count", 0) or 0)
    base = f"{base_name} ({status}, {seg_count} segs)"
    if status != "partial":
        return base

    unidentified = int(getattr(summary, "unidentified_speaker_count", 0) or 0)
    ignored = int(getattr(summary, "ignored_speaker_count", 0) or 0)
    return f"{base}, {unidentified} unidentified, {ignored} ignored"
