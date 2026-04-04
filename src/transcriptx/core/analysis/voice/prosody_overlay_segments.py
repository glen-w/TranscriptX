"""
v1 prosody overlay segment JSON for group aggregate temporal charts.

See ``docs/groups/group_charts_prosody_segment_artifact_v1.md``.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

PROSODY_OVERLAY_SEGMENTS_FILESTEM = "prosody_overlay_segments.v1"
PROSODY_OVERLAY_Y_FIELD = "rms_db"


def build_prosody_overlay_segments_v1_payload(
    segment_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build the on-disk payload from voice-feature-style rows (``start_s``, ``rms_db``).
    """
    out_segments: List[Dict[str, float]] = []

    def _start_key(r: Dict[str, Any]) -> float:
        s = r.get("start_s")
        if isinstance(s, (int, float)) and not isinstance(s, bool):
            return float(s)
        return 0.0

    for row in sorted(segment_rows, key=_start_key):
        st = row.get("start_s")
        rms = row.get(PROSODY_OVERLAY_Y_FIELD)
        if not isinstance(st, (int, float)) or isinstance(st, bool):
            continue
        if not isinstance(rms, (int, float)) or isinstance(rms, bool):
            continue
        fv, rv = float(st), float(rms)
        if not math.isfinite(fv) or not math.isfinite(rv):
            continue
        out_segments.append({"start": fv, PROSODY_OVERLAY_Y_FIELD: rv})

    return {
        "schema_version": 1,
        "y_field": PROSODY_OVERLAY_Y_FIELD,
        "segments": out_segments,
    }
