"""Logging configuration editor."""

from transcriptx.cli.settings import (
    SettingItem,
    create_bool_editor,
    create_choice_editor,
    create_float_editor,
    create_int_editor,
    create_str_editor,
    settings_menu_loop,
)
from ._dirty_tracker import is_dirty, mark_dirty


def edit_logging_config(config):
    """Edit logging configuration."""
    items = [
        SettingItem(
            order=1,
            key="logging.level",
            label="Log level",
            getter=lambda: config.logging.level,
            setter=lambda value: setattr(config.logging, "level", value),
            editor=create_choice_editor(
                ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                hint="Logging verbosity level.",
            ),
        ),
        SettingItem(
            order=2,
            key="logging.file_logging",
            label="File logging",
            getter=lambda: config.logging.file_logging,
            setter=lambda value: setattr(config.logging, "file_logging", value),
            editor=create_bool_editor(hint="Enable file logging."),
        ),
        SettingItem(
            order=3,
            key="logging.log_file",
            label="Log file",
            getter=lambda: config.logging.log_file,
            setter=lambda value: setattr(config.logging, "log_file", value),
            editor=create_str_editor(hint="Log file path."),
        ),
        SettingItem(
            order=4,
            key="logging.max_log_size_mb",
            label="Max log size (MB)",
            getter=lambda: config.logging.max_log_size / (1024 * 1024),
            setter=lambda value: setattr(
                config.logging, "max_log_size", int(float(value) * 1024 * 1024)
            ),
            editor=create_float_editor(min_val=1.0, hint="Maximum log size in MB."),
        ),
        SettingItem(
            order=5,
            key="logging.backup_count",
            label="Backup count",
            getter=lambda: config.logging.backup_count,
            setter=lambda value: setattr(config.logging, "backup_count", value),
            editor=create_int_editor(min_val=0, hint="Number of backup log files."),
        ),
    ]

    settings_menu_loop(
        title="📝 Logging Settings",
        items=items,
        on_back=lambda: None,
        dirty_tracker=is_dirty,
        mark_dirty=mark_dirty,
    )
