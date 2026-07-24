"""Apply canonical defaults to Charts gallery filter session state."""

from __future__ import annotations

from typing import Any, MutableMapping

from transcriptx.web.state import (
    CHARTS_CHART_TEXT_BOTH,
    CHARTS_CHART_TEXT_DESCRIPTION,
    CHARTS_CHART_TEXT_LLM,
    CHARTS_CHART_TEXT_NONE,
    CHARTS_FILTER_DEFAULTS,
    CHARTS_KEY_CHART_TEXT,
    CHARTS_KEY_EXPORT_RESULT,
    CHARTS_KEY_EXPORT_SIG,
    CHARTS_KEY_FILTER_SCOPE,
    CHARTS_KEY_FULL_SCREEN,
    CHARTS_KEY_KIND_PILLS,
    CHARTS_KEY_MODULE_SORT,
    CHARTS_KEY_OPEN_MODULES,
    CHARTS_KEY_SHOW_CHART_DESCRIPTIONS,
    CHARTS_KEY_SHOW_LLM_SUMMARIES,
    CHARTS_KEY_STATIC_TOGGLE,
    CHARTS_KEY_DYNAMIC_TOGGLE,
    CHARTS_KIND_DYNAMIC,
    CHARTS_KIND_STATIC,
    CHARTS_SORT_ALPHA,
    CHARTS_SORT_MODULE_FAMILY,
    CHARTS_VIEW_PREF_DEFAULTS,
    charts_resettable_keys,
    charts_run_change_reset_keys,
)

# One-shot migration marker for chart-text seeding from legacy toggles.
_CHARTS_CHART_TEXT_SEEDED = "tx_charts_chart_text_seeded_v1"


def _copy_default(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


def init_charts_open_modules(session_state: MutableMapping[str, Any]) -> list[str]:
    """Ensure open-modules is a fresh list owned by session state; return it."""
    current = session_state.get(CHARTS_KEY_OPEN_MODULES)
    if not isinstance(current, list):
        session_state[CHARTS_KEY_OPEN_MODULES] = []
        return session_state[CHARTS_KEY_OPEN_MODULES]
    return current


def clear_charts_ephemeral_state(session_state: MutableMapping[str, Any]) -> None:
    """Clear run-scoped ephemeral gallery state (open modules, export, fullscreen)."""
    session_state[CHARTS_KEY_OPEN_MODULES] = []
    session_state.pop(CHARTS_KEY_EXPORT_RESULT, None)
    session_state.pop(CHARTS_KEY_EXPORT_SIG, None)
    session_state[CHARTS_KEY_FULL_SCREEN] = None


def intersect_charts_open_modules(
    session_state: MutableMapping[str, Any],
    available_module_ids: set[str] | frozenset[str],
) -> list[str]:
    """Keep only open module ids that are still present; reassign (no in-place mutate)."""
    current = init_charts_open_modules(session_state)
    kept = [mid for mid in current if mid in available_module_ids]
    session_state[CHARTS_KEY_OPEN_MODULES] = kept
    return kept


def set_charts_open_modules(
    session_state: MutableMapping[str, Any], module_ids: list[str]
) -> None:
    """Replace the open-modules collection (always assign a new list)."""
    session_state[CHARTS_KEY_OPEN_MODULES] = list(module_ids)


def chart_text_from_legacy_toggles(show_descriptions: bool, show_llm: bool) -> str:
    """Map legacy description/LLM booleans to Chart text mode."""
    if show_descriptions and show_llm:
        return CHARTS_CHART_TEXT_BOTH
    if show_descriptions and not show_llm:
        return CHARTS_CHART_TEXT_DESCRIPTION
    if not show_descriptions and show_llm:
        return CHARTS_CHART_TEXT_LLM
    return CHARTS_CHART_TEXT_NONE


def chart_text_flags(chart_text: str) -> tuple[bool, bool]:
    """Return (show_registry_description, show_llm_summary) for Chart text mode."""
    if chart_text == CHARTS_CHART_TEXT_BOTH:
        return True, True
    if chart_text == CHARTS_CHART_TEXT_DESCRIPTION:
        return True, False
    if chart_text == CHARTS_CHART_TEXT_LLM:
        return False, True
    return False, False


def ensure_charts_chart_text(session_state: MutableMapping[str, Any]) -> str:
    """Seed Chart text once from legacy toggles; thereafter prefer the new key."""
    existing = session_state.get(CHARTS_KEY_CHART_TEXT)
    if isinstance(existing, str) and existing in {
        CHARTS_CHART_TEXT_NONE,
        CHARTS_CHART_TEXT_DESCRIPTION,
        CHARTS_CHART_TEXT_LLM,
        CHARTS_CHART_TEXT_BOTH,
    }:
        session_state[_CHARTS_CHART_TEXT_SEEDED] = True
        session_state.pop(CHARTS_KEY_SHOW_CHART_DESCRIPTIONS, None)
        session_state.pop(CHARTS_KEY_SHOW_LLM_SUMMARIES, None)
        return existing

    if not session_state.get(_CHARTS_CHART_TEXT_SEEDED):
        has_desc = CHARTS_KEY_SHOW_CHART_DESCRIPTIONS in session_state
        has_llm = CHARTS_KEY_SHOW_LLM_SUMMARIES in session_state
        if has_desc or has_llm:
            show_desc = bool(
                session_state.get(CHARTS_KEY_SHOW_CHART_DESCRIPTIONS, True)
            )
            show_llm = bool(session_state.get(CHARTS_KEY_SHOW_LLM_SUMMARIES, True))
            value = chart_text_from_legacy_toggles(show_desc, show_llm)
        else:
            value = CHARTS_VIEW_PREF_DEFAULTS[CHARTS_KEY_CHART_TEXT]
        session_state[CHARTS_KEY_CHART_TEXT] = value
        session_state[_CHARTS_CHART_TEXT_SEEDED] = True
        session_state.pop(CHARTS_KEY_SHOW_CHART_DESCRIPTIONS, None)
        session_state.pop(CHARTS_KEY_SHOW_LLM_SUMMARIES, None)
        return value

    value = CHARTS_VIEW_PREF_DEFAULTS[CHARTS_KEY_CHART_TEXT]
    session_state[CHARTS_KEY_CHART_TEXT] = value
    return value


# Back-compat alias used by older call sites / tests during migration.
def ensure_charts_display_toggles_default_on(
    session_state: MutableMapping[str, Any],
) -> None:
    """Ensure Chart text preference is seeded (replaces legacy display toggles)."""
    ensure_charts_chart_text(session_state)


def sync_kind_toggles_from_pills(session_state: MutableMapping[str, Any]) -> None:
    """Keep static/dynamic bools aligned with the kind pills selection."""
    selected = session_state.get(CHARTS_KEY_KIND_PILLS)
    if selected is None:
        selected = CHARTS_FILTER_DEFAULTS[CHARTS_KEY_KIND_PILLS]
    if isinstance(selected, str):
        selected = [selected]
    selected_set = set(selected or [])
    session_state[CHARTS_KEY_STATIC_TOGGLE] = CHARTS_KIND_STATIC in selected_set
    session_state[CHARTS_KEY_DYNAMIC_TOGGLE] = CHARTS_KIND_DYNAMIC in selected_set


def kind_filter_from_session(session_state: MutableMapping[str, Any]) -> str | None:
    """Derive ArtifactFilters kind from static/dynamic (or pills) session state."""
    sync_kind_toggles_from_pills(session_state)
    show_static = bool(session_state.get(CHARTS_KEY_STATIC_TOGGLE, True))
    show_dynamic = bool(session_state.get(CHARTS_KEY_DYNAMIC_TOGGLE, True))
    if show_static and show_dynamic:
        return None
    if show_static and not show_dynamic:
        return "chart_static"
    if not show_static and show_dynamic:
        return "chart_dynamic"
    return "__none__"


def ensure_charts_scope_filter(session_state: MutableMapping[str, Any]) -> str:
    """Normalize scope widget value; ``All`` / legacy ``None`` mean no scope filter."""
    raw = session_state.get(CHARTS_KEY_FILTER_SCOPE)
    if raw is None or raw == "":
        value = "All"
        session_state[CHARTS_KEY_FILTER_SCOPE] = value
        return value
    return str(raw)


def scope_filter_from_session(session_state: MutableMapping[str, Any]) -> str | None:
    """Return scope filter for ArtifactFilters (``None`` when All / unset)."""
    value = ensure_charts_scope_filter(session_state)
    if value == "All":
        return None
    return value


def _values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, list) and isinstance(right, list):
        return list(left) == list(right)
    return left == right


def charts_filters_are_dirty(session_state: MutableMapping[str, Any]) -> bool:
    """True when any resettable filter differs from CHARTS_FILTER_DEFAULTS."""
    for key in charts_resettable_keys():
        default = CHARTS_FILTER_DEFAULTS[key]
        current = session_state.get(key, default)
        if key == CHARTS_KEY_KIND_PILLS:
            # Normalize single-select / None from Streamlit widgets.
            if current is None:
                current = []
            elif isinstance(current, str):
                current = [current]
            default = list(default)
        if key == CHARTS_KEY_FILTER_SCOPE:
            # Legacy None and ``All`` both mean no scope filter.
            if current is None or current == "":
                current = "All"
            if default is None or default == "":
                default = "All"
        if not _values_equal(current, default):
            return True
    return False


def _apply_filter_defaults(
    session_state: MutableMapping[str, Any],
    keys: list[str],
) -> None:
    for key in keys:
        if key in CHARTS_FILTER_DEFAULTS:
            session_state[key] = _copy_default(CHARTS_FILTER_DEFAULTS[key])
    sync_kind_toggles_from_pills(session_state)


def reset_charts_filters_to_defaults(session_state: MutableMapping[str, Any]) -> None:
    """Hard reset: every resettable filter → default; clear ephemeral; keep chart text."""
    _apply_filter_defaults(session_state, charts_resettable_keys())
    clear_charts_ephemeral_state(session_state)
    ensure_charts_chart_text(session_state)


def reset_charts_filters_for_run_change(
    session_state: MutableMapping[str, Any],
) -> None:
    """Run change: reset filters except sort; clear ephemeral; keep chart text + sort."""
    preserved_sort = session_state.get(CHARTS_KEY_MODULE_SORT)
    _apply_filter_defaults(session_state, charts_run_change_reset_keys())
    if preserved_sort in {CHARTS_SORT_ALPHA, CHARTS_SORT_MODULE_FAMILY}:
        session_state[CHARTS_KEY_MODULE_SORT] = preserved_sort
    clear_charts_ephemeral_state(session_state)
    ensure_charts_chart_text(session_state)
