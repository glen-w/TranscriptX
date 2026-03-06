"""Highlights configuration editor."""

from typing import Any

from transcriptx.cli.settings import settings_menu_loop  # type: ignore[import-untyped]
from transcriptx.cli.settings.generate import (  # type: ignore[import-untyped]
    build_setting_items_from_dataclass,
)

from ._dirty_tracker import is_dirty, mark_dirty


def edit_highlights_config(config: Any) -> None:
    """Edit highlights configuration."""
    highlights_cfg = getattr(getattr(config, "analysis", None), "highlights", None)
    if highlights_cfg is None:
        return

    items = build_setting_items_from_dataclass(
        highlights_cfg, prefix="analysis.highlights"
    )
    settings_menu_loop(
        title="✨ Highlights Settings",
        items=items,
        on_back=lambda: None,
        dirty_tracker=is_dirty,
        mark_dirty=mark_dirty,
    )
