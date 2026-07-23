"""Charts filter reset uses centralized defaults from ``state``."""

from __future__ import annotations

from transcriptx.web.charts_filter_state import (
    chart_text_flags,
    chart_text_from_legacy_toggles,
    charts_filters_are_dirty,
    ensure_charts_chart_text,
    intersect_charts_open_modules,
    reset_charts_filters_for_run_change,
    reset_charts_filters_to_defaults,
    set_charts_open_modules,
)
from transcriptx.web.state import (
    CHARTS_CHART_TEXT_BOTH,
    CHARTS_CHART_TEXT_DESCRIPTION,
    CHARTS_CHART_TEXT_LLM,
    CHARTS_CHART_TEXT_NONE,
    CHARTS_FILTER_DEFAULTS,
    CHARTS_KEY_CHART_TEXT,
    CHARTS_KEY_FILTER_MODULE,
    CHARTS_KEY_FILTER_TAGS,
    CHARTS_KEY_MODULE_SORT,
    CHARTS_KEY_OPEN_MODULES,
    CHARTS_KEY_SEARCH,
    CHARTS_KEY_SHOW_CHART_DESCRIPTIONS,
    CHARTS_KEY_SHOW_LLM_SUMMARIES,
    CHARTS_KEY_SOURCE_PRESET,
    CHARTS_KEY_TAGS_MULTI,
    CHARTS_SORT_ALPHA,
    CHARTS_SORT_MODULE_FAMILY,
    charts_resettable_keys,
)


def test_charts_resettable_keys_cover_defaults() -> None:
    for k in charts_resettable_keys():
        assert k in CHARTS_FILTER_DEFAULTS
    assert CHARTS_KEY_CHART_TEXT not in charts_resettable_keys()
    assert CHARTS_KEY_OPEN_MODULES not in charts_resettable_keys()


def test_reset_charts_filters_to_defaults_applies_values() -> None:
    session: dict = {
        CHARTS_KEY_FILTER_MODULE: "noise",
        CHARTS_KEY_FILTER_TAGS: ["x"],
        CHARTS_KEY_SOURCE_PRESET: "Member sessions",
        CHARTS_KEY_SEARCH: "tension",
        CHARTS_KEY_MODULE_SORT: CHARTS_SORT_ALPHA,
        CHARTS_KEY_CHART_TEXT: CHARTS_CHART_TEXT_NONE,
        CHARTS_KEY_OPEN_MODULES: ["acts"],
    }
    reset_charts_filters_to_defaults(session)
    assert (
        session[CHARTS_KEY_FILTER_MODULE]
        == CHARTS_FILTER_DEFAULTS[CHARTS_KEY_FILTER_MODULE]
    )
    assert session[CHARTS_KEY_FILTER_TAGS] == []
    assert session[CHARTS_KEY_SOURCE_PRESET] == "All"
    assert session[CHARTS_KEY_SEARCH] == ""
    assert session[CHARTS_KEY_MODULE_SORT] == CHARTS_SORT_MODULE_FAMILY
    assert session[CHARTS_KEY_OPEN_MODULES] == []
    # Reset preserves chart text preference.
    assert session[CHARTS_KEY_CHART_TEXT] == CHARTS_CHART_TEXT_NONE


def test_charts_filters_are_dirty_ignores_open_modules_and_chart_text() -> None:
    session: dict = dict(CHARTS_FILTER_DEFAULTS)
    for key, value in list(session.items()):
        if isinstance(value, list):
            session[key] = list(value)
    session[CHARTS_KEY_OPEN_MODULES] = ["acts"]
    session[CHARTS_KEY_CHART_TEXT] = CHARTS_CHART_TEXT_NONE
    assert charts_filters_are_dirty(session) is False
    session[CHARTS_KEY_SEARCH] = "x"
    assert charts_filters_are_dirty(session) is True


def test_kind_filter_both_deselected_is_none_sentinel() -> None:
    from transcriptx.web.charts_filter_state import kind_filter_from_session
    from transcriptx.web.state import (
        CHARTS_KEY_DYNAMIC_TOGGLE,
        CHARTS_KEY_KIND_PILLS,
        CHARTS_KEY_STATIC_TOGGLE,
    )

    session: dict = {
        CHARTS_KEY_KIND_PILLS: [],
        CHARTS_KEY_STATIC_TOGGLE: True,
        CHARTS_KEY_DYNAMIC_TOGGLE: True,
    }
    assert kind_filter_from_session(session) == "__none__"
    assert session[CHARTS_KEY_STATIC_TOGGLE] is False
    assert session[CHARTS_KEY_DYNAMIC_TOGGLE] is False


def test_run_change_preserves_sort_clears_open_modules() -> None:
    session: dict = {
        CHARTS_KEY_FILTER_MODULE: "noise",
        CHARTS_KEY_MODULE_SORT: CHARTS_SORT_ALPHA,
        CHARTS_KEY_OPEN_MODULES: ["acts", "stats"],
        CHARTS_KEY_CHART_TEXT: CHARTS_CHART_TEXT_DESCRIPTION,
    }
    reset_charts_filters_for_run_change(session)
    assert session[CHARTS_KEY_FILTER_MODULE] is None
    assert session[CHARTS_KEY_MODULE_SORT] == CHARTS_SORT_ALPHA
    assert session[CHARTS_KEY_OPEN_MODULES] == []
    assert session[CHARTS_KEY_CHART_TEXT] == CHARTS_CHART_TEXT_DESCRIPTION


def test_chart_text_legacy_migration_all_four_mappings() -> None:
    assert chart_text_from_legacy_toggles(True, True) == CHARTS_CHART_TEXT_BOTH
    assert chart_text_from_legacy_toggles(True, False) == CHARTS_CHART_TEXT_DESCRIPTION
    assert chart_text_from_legacy_toggles(False, True) == CHARTS_CHART_TEXT_LLM
    assert chart_text_from_legacy_toggles(False, False) == CHARTS_CHART_TEXT_NONE
    assert chart_text_flags(CHARTS_CHART_TEXT_BOTH) == (True, True)
    assert chart_text_flags(CHARTS_CHART_TEXT_NONE) == (False, False)


def test_ensure_charts_chart_text_migrates_once_then_ignores_legacy() -> None:
    session: dict = {
        CHARTS_KEY_SHOW_CHART_DESCRIPTIONS: False,
        CHARTS_KEY_SHOW_LLM_SUMMARIES: True,
    }
    assert ensure_charts_chart_text(session) == CHARTS_CHART_TEXT_LLM
    assert session[CHARTS_KEY_CHART_TEXT] == CHARTS_CHART_TEXT_LLM
    assert CHARTS_KEY_SHOW_CHART_DESCRIPTIONS not in session
    assert CHARTS_KEY_SHOW_LLM_SUMMARIES not in session

    session[CHARTS_KEY_SHOW_LLM_SUMMARIES] = False
    assert ensure_charts_chart_text(session) == CHARTS_CHART_TEXT_LLM


def test_intersect_open_modules_reassigns() -> None:
    session: dict = {}
    set_charts_open_modules(session, ["acts", "gone", "stats"])
    kept = intersect_charts_open_modules(session, frozenset({"acts", "stats"}))
    assert kept == ["acts", "stats"]
    assert session[CHARTS_KEY_OPEN_MODULES] == ["acts", "stats"]


def test_source_preset_tags_cleared_from_dirty_when_reset() -> None:
    session: dict = {
        CHARTS_KEY_SOURCE_PRESET: "Group aggregate",
        CHARTS_KEY_FILTER_TAGS: ["group_aggregate"],
        CHARTS_KEY_TAGS_MULTI: ["foo"],
    }
    assert charts_filters_are_dirty(session) is True
    reset_charts_filters_to_defaults(session)
    assert session[CHARTS_KEY_TAGS_MULTI] == []
    assert charts_filters_are_dirty(session) is False
