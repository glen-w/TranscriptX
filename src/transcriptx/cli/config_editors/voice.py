"""Voice configuration editor."""

from typing import Any

from transcriptx.cli.settings import settings_menu_loop  # type: ignore[import-untyped]
from transcriptx.cli.settings.generate import (  # type: ignore[import-untyped]
    build_setting_items_from_dataclass,
)

from ._dirty_tracker import is_dirty, mark_dirty


def edit_voice_config(config: Any) -> None:
    """Edit voice modality configuration."""
    voice_cfg = getattr(getattr(config, "analysis", None), "voice", None)
    if voice_cfg is None:
        # Config shape mismatch; nothing to edit.
        return

    items = build_setting_items_from_dataclass(voice_cfg, prefix="analysis.voice")

    settings_menu_loop(
        title="🗣️ Voice Settings",
        items=items,
        on_back=lambda: None,
        dirty_tracker=is_dirty,
        mark_dirty=mark_dirty,
    )
