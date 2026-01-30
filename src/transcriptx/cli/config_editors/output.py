"""Output configuration editor."""

from transcriptx.cli.settings import (
    SettingItem,
    create_bool_editor,
    create_choice_editor,
    create_float_editor,
    create_str_editor,
    settings_menu_loop,
)
from ._dirty_tracker import is_dirty, mark_dirty


def edit_output_config(config):
    """Edit output configuration."""
    items = [
        SettingItem(
            order=1,
            key="output.base_output_dir",
            label="Base output directory",
            getter=lambda: config.output.base_output_dir,
            setter=lambda value: setattr(config.output, "base_output_dir", value),
            editor=create_str_editor(hint="Base directory for analysis outputs."),
        ),
        SettingItem(
            order=2,
            key="output.default_audio_folder",
            label="Default audio folder",
            getter=lambda: config.output.default_audio_folder,
            setter=lambda value: setattr(config.output, "default_audio_folder", value),
            editor=create_str_editor(hint="Starting folder for audio selection."),
        ),
        SettingItem(
            order=3,
            key="output.default_transcript_folder",
            label="Default transcript folder",
            getter=lambda: config.output.default_transcript_folder,
            setter=lambda value: setattr(
                config.output, "default_transcript_folder", value
            ),
            editor=create_str_editor(hint="Starting folder for transcript selection."),
        ),
        SettingItem(
            order=4,
            key="output.default_readable_transcript_folder",
            label="Default readable transcript folder",
            getter=lambda: config.output.default_readable_transcript_folder,
            setter=lambda value: setattr(
                config.output, "default_readable_transcript_folder", value
            ),
            editor=create_str_editor(
                hint="Starting folder for readable transcript selection."
            ),
        ),
        SettingItem(
            order=5,
            key="output.create_subdirectories",
            label="Create subdirectories",
            getter=lambda: config.output.create_subdirectories,
            setter=lambda value: setattr(config.output, "create_subdirectories", value),
            editor=create_bool_editor(
                hint="Create organized subfolders for analysis outputs."
            ),
        ),
        SettingItem(
            order=6,
            key="output.overwrite_existing",
            label="Overwrite existing files",
            getter=lambda: config.output.overwrite_existing,
            setter=lambda value: setattr(config.output, "overwrite_existing", value),
            editor=create_bool_editor(hint="Replace existing output files."),
        ),
        SettingItem(
            order=7,
            key="output.dynamic_charts",
            label="Dynamic charts",
            getter=lambda: getattr(config.output, "dynamic_charts", "auto"),
            setter=lambda value: setattr(config.output, "dynamic_charts", value),
            editor=create_choice_editor(
                choices=["auto", "on", "off"],
                hint="auto=dynamic if Plotly installed; on=fail if missing; off=never.",
            ),
        ),
        SettingItem(
            order=8,
            key="output.dynamic_views",
            label="Dynamic views",
            getter=lambda: getattr(config.output, "dynamic_views", "auto"),
            setter=lambda value: setattr(config.output, "dynamic_views", value),
            editor=create_choice_editor(
                choices=["auto", "on", "off"],
                hint="auto=HTML views (table fallback if Plotly missing); on=require Plotly; off=never.",
            ),
        ),
        SettingItem(
            order=9,
            key="output.audio_deduplication_threshold",
            label="Audio deduplication threshold",
            getter=lambda: config.output.audio_deduplication_threshold,
            setter=lambda value: setattr(
                config.output, "audio_deduplication_threshold", value
            ),
            editor=create_float_editor(
                min_val=0.0,
                max_val=1.0,
                hint="Similarity threshold (0.0 to 1.0).",
            ),
        ),
    ]

    settings_menu_loop(
        title="📁 Output Settings",
        items=items,
        on_back=lambda: None,
        dirty_tracker=is_dirty,
        mark_dirty=mark_dirty,
    )
