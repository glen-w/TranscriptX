"""Opaque chart_key digests from stable logical-chart provenance."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


def _canon(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {
            str(k): _canon(v)
            for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canon(v) for v in value]
    return str(value)


def build_chart_key_payload(
    *,
    run_target_id: str,
    logical_chart_id: str,
    viz_id: str,
    scope: str,
    speaker_identity: str | None,
    slice_identity: str | None,
    source_run_id: str | None,
    member_session_id: str | None,
) -> dict[str, Any]:
    """Format-independent logical key inputs (no PNG/HTML presence)."""
    return {
        "run_target_id": run_target_id or "",
        "logical_chart_id": logical_chart_id or "",
        "viz_id": viz_id or "",
        "scope": scope or "global",
        "speaker_identity": speaker_identity or "",
        "slice_identity": slice_identity or "",
        "source_run_id": source_run_id or "",
        "member_session_id": member_session_id or "",
    }


def chart_key_digest(payload: Mapping[str, Any]) -> str:
    """Opaque hex digest used in filenames — never safe_viz_id."""
    canonical = json.dumps(_canon(dict(payload)), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_logical_chart_id(
    *,
    module: str,
    viz_id: str,
    scope: str,
    speaker_identity: str | None,
    name: str | None = None,
) -> str:
    """Stable logical chart id independent of render format."""
    parts = [
        module or "",
        viz_id or "",
        scope or "global",
        speaker_identity or "",
        name or "",
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
