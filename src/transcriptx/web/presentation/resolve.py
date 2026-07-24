"""Canonical presentation-mode resolver and save helper."""

from __future__ import annotations

from typing import Any

from transcriptx.web.presentation.prefs import (
    MODE_FULL,
    MODE_GUIDED,
    PresentationMode,
    SaveResult,
    VALID_MODES,
    get_cached_presentation_prefs,
    invalidate_presentation_cache,
    load_presentation_prefs,
    save_presentation_prefs,
)
from transcriptx.web.presentation.seed import seed_presentation_mode_if_needed

MODE_LABELS: dict[str, str] = {
    MODE_GUIDED: "Guided",
    MODE_FULL: "Full controls",
}
WIDGET_KEY = "presentation_mode_widget"
PENDING_SYNC_KEY = "presentation_mode_pending_sync"


def ensure_presentation_mode_seeded() -> PresentationMode:
    return seed_presentation_mode_if_needed()


def resolve_presentation_mode() -> PresentationMode:
    """Sole authority for Guided / Full controls at runtime."""
    ensure_presentation_mode_seeded()
    return get_cached_presentation_prefs().mode


def set_presentation_mode(
    mode: str,
    *,
    path: Any = None,
) -> SaveResult:
    if mode not in VALID_MODES:
        return SaveResult(ok=False, error=f"Unknown presentation mode: {mode!r}")
    prefs, draft = load_presentation_prefs(path)
    if draft.recovery:
        return SaveResult(
            ok=False,
            error=draft.recovery_message or "Presentation mode file is in recovery.",
        )
    if prefs.mode == mode:
        return SaveResult(ok=True)
    draft.prefs.mode = mode  # type: ignore[assignment]
    result = save_presentation_prefs(draft, path=path)
    if result.ok:
        invalidate_presentation_cache()
    return result
