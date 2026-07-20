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
    # Gallery description/summary toggles live in CHARTS_FILTER_DEFAULTS for
    # initial values but are intentionally not reset with filters.
    for k in charts_resettable_keys():
        assert k in CHARTS_FILTER_DEFAULTS


def test_reset_charts_filters_to_defaults_applies_values() -> None:
    from transcriptx.web.state import (
        CHARTS_KEY_SHOW_CHART_DESCRIPTIONS,
        CHARTS_KEY_SHOW_LLM_SUMMARIES,
    )

    session: dict = {
        CHARTS_KEY_FILTER_MODULE: "noise",
        CHARTS_KEY_FILTER_TAGS: ["x"],
        CHARTS_KEY_SOURCE_PRESET: "Member sessions",
        CHARTS_KEY_EXPAND_ALL: True,
        CHARTS_KEY_SHOW_CHART_DESCRIPTIONS: False,
        CHARTS_KEY_SHOW_LLM_SUMMARIES: False,
    }
    reset_charts_filters_to_defaults(session)
    assert (
        session[CHARTS_KEY_FILTER_MODULE]
        == CHARTS_FILTER_DEFAULTS[CHARTS_KEY_FILTER_MODULE]
    )
    assert session[CHARTS_KEY_FILTER_TAGS] == []
    assert session[CHARTS_KEY_SOURCE_PRESET] == "All"
    assert session[CHARTS_KEY_EXPAND_ALL] is False
    # Reset filters preserves explicit display-toggle choices.
    assert session[CHARTS_KEY_SHOW_CHART_DESCRIPTIONS] is False
    assert session[CHARTS_KEY_SHOW_LLM_SUMMARIES] is False


def test_ensure_charts_display_toggles_default_on_migrates_once() -> None:
    from transcriptx.web.charts_filter_state import (
        ensure_charts_display_toggles_default_on,
    )
    from transcriptx.web.state import (
        CHARTS_KEY_SHOW_CHART_DESCRIPTIONS,
        CHARTS_KEY_SHOW_LLM_SUMMARIES,
    )

    session: dict = {
        CHARTS_KEY_SHOW_CHART_DESCRIPTIONS: False,
        CHARTS_KEY_SHOW_LLM_SUMMARIES: False,
    }
    ensure_charts_display_toggles_default_on(session)
    assert session[CHARTS_KEY_SHOW_CHART_DESCRIPTIONS] is True
    assert session[CHARTS_KEY_SHOW_LLM_SUMMARIES] is True

    session[CHARTS_KEY_SHOW_LLM_SUMMARIES] = False
    ensure_charts_display_toggles_default_on(session)
    # Subsequent calls do not override user choice.
    assert session[CHARTS_KEY_SHOW_LLM_SUMMARIES] is False
