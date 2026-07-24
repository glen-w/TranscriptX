"""Guided / Full controls presentation preferences."""

from __future__ import annotations

from transcriptx.web.presentation.prefs import (
    MODE_FULL,
    MODE_GUIDED,
    PRESENTATION_FILENAME,
    PRESENTATION_SCHEMA_VERSION,
    PresentationDraft,
    PresentationMode,
    PresentationPrefs,
    SaveResult,
    built_in_prefs,
    get_cached_presentation_prefs,
    invalidate_presentation_cache,
    load_presentation_prefs,
    presentation_prefs_path,
    replace_with_built_in_defaults,
    save_presentation_prefs,
)
from transcriptx.web.presentation.resolve import (
    MODE_LABELS,
    WIDGET_KEY,
    ensure_presentation_mode_seeded,
    resolve_presentation_mode,
    set_presentation_mode,
)
from transcriptx.web.presentation.seed import (
    seed_presentation_mode_if_needed,
    workspace_looks_existing,
)
from transcriptx.web.presentation.visibility import (
    FULL_ONLY_PAGE_KEYS,
    GUIDED_SETTINGS_TABS,
    page_visible_in_presentation,
    render_full_only_unlock_banner,
    visible_pages_in_section,
)

__all__ = [
    "FULL_ONLY_PAGE_KEYS",
    "GUIDED_SETTINGS_TABS",
    "MODE_FULL",
    "MODE_GUIDED",
    "MODE_LABELS",
    "PRESENTATION_FILENAME",
    "PRESENTATION_SCHEMA_VERSION",
    "PresentationDraft",
    "PresentationMode",
    "PresentationPrefs",
    "SaveResult",
    "WIDGET_KEY",
    "built_in_prefs",
    "ensure_presentation_mode_seeded",
    "get_cached_presentation_prefs",
    "invalidate_presentation_cache",
    "load_presentation_prefs",
    "page_visible_in_presentation",
    "presentation_prefs_path",
    "render_full_only_unlock_banner",
    "replace_with_built_in_defaults",
    "resolve_presentation_mode",
    "save_presentation_prefs",
    "seed_presentation_mode_if_needed",
    "set_presentation_mode",
    "visible_pages_in_section",
    "workspace_looks_existing",
]
