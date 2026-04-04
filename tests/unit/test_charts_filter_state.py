"""Charts filter reset uses centralized defaults from ``state``."""

from __future__ import annotations

from transcriptx.web.charts_filter_state import reset_charts_filters_to_defaults
from transcriptx.web.state import (
    CHARTS_FILTER_DEFAULTS,
    CHARTS_KEY_EXPAND_ALL,
    CHARTS_KEY_FILTER_MODULE,
    CHARTS_KEY_FILTER_TAGS,
    CHARTS_KEY_SOURCE_PRESET,
    charts_resettable_keys,
)


def test_charts_resettable_keys_cover_defaults() -> None:
    for k in CHARTS_FILTER_DEFAULTS:
        assert k in charts_resettable_keys()


def test_reset_charts_filters_to_defaults_applies_values() -> None:
    session: dict = {
        CHARTS_KEY_FILTER_MODULE: "noise",
        CHARTS_KEY_FILTER_TAGS: ["x"],
        CHARTS_KEY_SOURCE_PRESET: "Member sessions",
        CHARTS_KEY_EXPAND_ALL: True,
    }
    reset_charts_filters_to_defaults(session)
    assert (
        session[CHARTS_KEY_FILTER_MODULE]
        == CHARTS_FILTER_DEFAULTS[CHARTS_KEY_FILTER_MODULE]
    )
    assert session[CHARTS_KEY_FILTER_TAGS] == []
    assert session[CHARTS_KEY_SOURCE_PRESET] == "All"
    assert session[CHARTS_KEY_EXPAND_ALL] is False
