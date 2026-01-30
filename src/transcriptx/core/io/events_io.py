"""Event IO helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from transcriptx.core.models.events import Event, sort_events_deterministically
from transcriptx.io import save_json
from transcriptx.core.presentation import format_segment_anchor


def _resolve_output_dir(output_structure, output_dir: Optional[Path] = None) -> Path:
    if output_dir:
        return Path(output_dir)
    if hasattr(output_structure, "global_data_dir"):
        return Path(output_structure.global_data_dir)
    if hasattr(output_structure, "data_dir"):
        return Path(output_structure.data_dir)
    return Path(output_structure)


def save_events_json(
    events: Iterable[Event],
    output_structure,
    filename: str,
    output_dir: Optional[Path] = None,
    sort_events: bool = True,
    provenance: Optional[Dict[str, Any]] = None,
) -> Path:
    """Save events to JSON file in a deterministic order."""
    output_path = _resolve_output_dir(output_structure, output_dir) / filename
    event_list = list(events)
    if sort_events:
        event_list = sort_events_deterministically(event_list)

    payload: List[Dict[str, Any]] = []
    for event in event_list:
        event_payload = event.to_dict()
        segment_indexes: List[int] = []
        if event.segment_start_idx is not None:
            segment_indexes.append(int(event.segment_start_idx))
        if (
            event.segment_end_idx is not None
            and event.segment_end_idx != event.segment_start_idx
        ):
            segment_indexes.append(int(event.segment_end_idx))
        if segment_indexes:
            event_payload["segment_ref"] = {"segment_indexes": segment_indexes}
            event_payload["anchor"] = format_segment_anchor(
                start=event.time_start,
                end=event.time_end,
                speaker=event.speaker,
                segment_indexes=segment_indexes,
            )
            event_payload["status"] = "ok"
        if provenance:
            event_payload["provenance"] = provenance
        payload.append(event_payload)

    save_json(payload, str(output_path))
    return output_path


def load_events_json(path: str | Path) -> List[Event]:
    """Load events from a JSON file."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        return []
    return [Event.from_dict(item) for item in data]
