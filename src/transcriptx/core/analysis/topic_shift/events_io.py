"""Load topic_shift events envelope (never pass through bare load_events_json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

from transcriptx.core.analysis.topic_shift.schemas import EventsEnvelopeModel
from transcriptx.core.models.events import Event


def load_topic_shift_events(path: str | Path) -> List[Event]:
    """Unwrap versioned events envelope into Event list."""
    p = Path(path)
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(raw, dict):
        return []
    try:
        env = EventsEnvelopeModel.model_validate(raw)
    except Exception:
        return []
    return [Event.from_dict(e.model_dump()) for e in env.events]


def load_topic_shift_events_envelope(path: str | Path) -> dict[str, Any] | None:
    p = Path(path)
    if not p.is_file():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return EventsEnvelopeModel.model_validate(raw).model_dump(mode="json")
    except Exception:
        return None
