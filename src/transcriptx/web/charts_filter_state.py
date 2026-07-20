"""Apply canonical defaults to Charts gallery filter session state."""

from __future__ import annotations

from typing import Any, MutableMapping

from transcriptx.web.state import (
    CHARTS_FILTER_DEFAULTS,
    CHARTS_KEY_SHOW_CHART_DESCRIPTIONS,
    CHARTS_KEY_SHOW_LLM_SUMMARIES,
    charts_resettable_keys,
)

# Display-only gallery toggles: default on, but not cleared by "Reset filters".
_CHARTS_DISPLAY_TOGGLE_KEYS = (
    CHARTS_KEY_SHOW_CHART_DESCRIPTIONS,
    CHARTS_KEY_SHOW_LLM_SUMMARIES,
)

# One-shot migration: older sessions inherited Streamlit's False toggle default
# because these keys were never seeded before the widget rendered.
_CHARTS_DISPLAY_TOGGLES_SEEDED = "tx_charts_display_toggles_seeded_v1"


def seed_charts_display_toggles(
    session_state: MutableMapping[str, Any],
    *,
    force: bool = False,
) -> None:
    """Ensure description/LLM toggles default on before Streamlit widgets run.

    ``force=True`` overwrites existing values (new-run init / one-shot migration).
    ``force=False`` only fills missing keys so "Reset filters" preserves the user's
    display choices.
    """
    for key in _CHARTS_DISPLAY_TOGGLE_KEYS:
        if (force or key not in session_state) and key in CHARTS_FILTER_DEFAULTS:
            session_state[key] = CHARTS_FILTER_DEFAULTS[key]


def ensure_charts_display_toggles_default_on(
    session_state: MutableMapping[str, Any],
) -> None:
    """Seed missing toggles; once per browser session, force defaults on."""
    if not session_state.get(_CHARTS_DISPLAY_TOGGLES_SEEDED):
        seed_charts_display_toggles(session_state, force=True)
        session_state[_CHARTS_DISPLAY_TOGGLES_SEEDED] = True
    else:
        seed_charts_display_toggles(session_state, force=False)


def reset_charts_filters_to_defaults(session_state: MutableMapping[str, Any]) -> None:
    """Hard reset: every resettable charts filter key → value from CHARTS_FILTER_DEFAULTS."""
    for key in charts_resettable_keys():
        if key in CHARTS_FILTER_DEFAULTS:
            # Copy lists so callers don't mutate shared defaults
            val = CHARTS_FILTER_DEFAULTS[key]
            session_state[key] = list(val) if isinstance(val, list) else val
    seed_charts_display_toggles(session_state, force=False)
