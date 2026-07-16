"""Shared dynamics artifact writes: dirs, events, stats, speaker stats.

Callers must call :func:`ensure_dynamics_dirs` before write helpers.
Summary construction stays module-owned via ``output_service.save_summary``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable, List, Mapping

from transcriptx.core.io.events_io import save_events_json
from transcriptx.core.utils.validation import sanitize_filename
from transcriptx.io import save_json


def ensure_dynamics_dirs(
    output_structure: Any, *, include_speaker_data: bool = False
) -> None:
    """Create global data/charts dirs; optionally speaker data (pauses)."""
    os.makedirs(output_structure.global_data_dir, exist_ok=True)
    os.makedirs(output_structure.global_charts_dir, exist_ok=True)
    if include_speaker_data:
        os.makedirs(output_structure.speaker_data_dir, exist_ok=True)


def write_events_and_stats(
    output_structure: Any,
    module_name: str,
    events: Iterable[Any],
    stats: Mapping[str, Any],
) -> tuple[Path, Path]:
    """Write ``{module}.events.json`` then ``{module}.stats.json``. Assumes dirs exist."""
    events_path = save_events_json(
        events, output_structure, f"{module_name}.events.json"
    )
    stats_path = output_structure.global_data_dir / f"{module_name}.stats.json"
    save_json(dict(stats), str(stats_path))
    return events_path, Path(stats_path)


def write_speaker_stats_files(
    output_structure: Any,
    module_name: str,
    speaker_stats: Mapping[str, Any],
) -> list[Path]:
    """Write per-speaker stats JSON; no speaker skip filter (matches pauses)."""
    written: List[Path] = []
    for speaker, data in speaker_stats.items():
        safe_speaker = sanitize_filename(str(speaker) if speaker is not None else "")
        path = (
            output_structure.speaker_data_dir
            / f"{safe_speaker}_{module_name}.stats.json"
        )
        save_json(data, str(path))
        written.append(Path(path))
    return written
