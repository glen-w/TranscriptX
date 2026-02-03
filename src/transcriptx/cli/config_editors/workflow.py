"""Workflow / CLI configuration editor."""

from __future__ import annotations

from typing import Any

from transcriptx.cli.settings import (
    SettingItem,
    create_bool_editor,
    create_str_editor,
    settings_menu_loop,
)
from ._dirty_tracker import is_dirty, mark_dirty


def edit_workflow_config(config: Any) -> None:
    """Edit workflow / CLI configuration."""
    items = [
        SettingItem(
            order=1,
            key="workflow.cli_pruning_enabled",
            label="Pruning features (Post-processing menu)",
            getter=lambda: config.workflow.cli_pruning_enabled,
            setter=lambda value: setattr(config.workflow, "cli_pruning_enabled", value),
            editor=create_bool_editor(
                hint="When ON, the Post-processing menu shows 'Prune old runs (DB only)' and 'Prune old runs (DB + outputs)'. Off by default.",
            ),
        ),
        SettingItem(
            order=2,
            key="workflow.default_config_save_path",
            label="Default config save path",
            getter=lambda: config.workflow.default_config_save_path or "",
            setter=lambda value: setattr(
                config.workflow, "default_config_save_path", (value or "").strip()
            ),
            editor=create_str_editor(
                hint="Path pre-filled when saving config. Leave empty to use the project config path (.transcriptx/config.json).",
            ),
        ),
    ]

    settings_menu_loop(
        title="⚙️ Workflow / CLI Settings",
        items=items,
        on_back=lambda: None,
        dirty_tracker=is_dirty,
        mark_dirty=mark_dirty,
    )
