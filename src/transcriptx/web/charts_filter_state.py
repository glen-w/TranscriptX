"""Apply canonical defaults to Charts gallery filter session state."""

from __future__ import annotations

from typing import Any, MutableMapping

from transcriptx.web.state import CHARTS_FILTER_DEFAULTS, charts_resettable_keys


def reset_charts_filters_to_defaults(session_state: MutableMapping[str, Any]) -> None:
    """Hard reset: every resettable charts filter key → value from CHARTS_FILTER_DEFAULTS."""
    for key in charts_resettable_keys():
        if key in CHARTS_FILTER_DEFAULTS:
            # Copy lists so callers don't mutate shared defaults
            val = CHARTS_FILTER_DEFAULTS[key]
            session_state[key] = list(val) if isinstance(val, list) else val
