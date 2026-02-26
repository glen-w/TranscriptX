"""Group analysis configuration editor."""

from transcriptx.cli.settings import (
    SettingItem,
    create_bool_editor,
    create_str_editor,
    settings_menu_loop,
)
from ._dirty_tracker import is_dirty, mark_dirty


def edit_group_analysis_config(config):
    """Edit group analysis configuration."""
    items = [
        SettingItem(
            order=1,
            key="group_analysis.enabled",
            label="Enabled",
            getter=lambda: config.group_analysis.enabled,
            setter=lambda value: setattr(config.group_analysis, "enabled", value),
            editor=create_bool_editor(hint="Enable group analysis features."),
        ),
        SettingItem(
            order=2,
            key="group_analysis.output_dir",
            label="Group output directory",
            getter=lambda: config.group_analysis.output_dir,
            setter=lambda value: setattr(config.group_analysis, "output_dir", value),
            editor=create_str_editor(hint="Base directory for group outputs."),
        ),
        SettingItem(
            order=3,
            key="group_analysis.persist_groups",
            label="Persist groups",
            getter=lambda: config.group_analysis.persist_groups,
            setter=lambda value: setattr(
                config.group_analysis, "persist_groups", value
            ),
            editor=create_bool_editor(
                hint="Persist TranscriptSets to database by default."
            ),
        ),
        SettingItem(
            order=4,
            key="group_analysis.enable_stats_aggregation",
            label="Stats aggregation",
            getter=lambda: config.group_analysis.enable_stats_aggregation,
            setter=lambda value: setattr(
                config.group_analysis, "enable_stats_aggregation", value
            ),
            editor=create_bool_editor(hint="Enable stats aggregation."),
        ),
        SettingItem(
            order=5,
            key="group_analysis.scaffold_by_session",
            label="Scaffold by session",
            getter=lambda: config.group_analysis.scaffold_by_session,
            setter=lambda value: setattr(
                config.group_analysis, "scaffold_by_session", value
            ),
            editor=create_bool_editor(hint="Create by_session scaffold folders."),
        ),
        SettingItem(
            order=6,
            key="group_analysis.scaffold_by_speaker",
            label="Scaffold by speaker",
            getter=lambda: config.group_analysis.scaffold_by_speaker,
            setter=lambda value: setattr(
                config.group_analysis, "scaffold_by_speaker", value
            ),
            editor=create_bool_editor(hint="Create by_speaker scaffold folders."),
        ),
        SettingItem(
            order=7,
            key="group_analysis.scaffold_comparisons",
            label="Scaffold comparisons",
            getter=lambda: config.group_analysis.scaffold_comparisons,
            setter=lambda value: setattr(
                config.group_analysis, "scaffold_comparisons", value
            ),
            editor=create_bool_editor(hint="Create comparisons scaffold folders."),
        ),
    ]

    settings_menu_loop(
        title="👥 Group Analysis Settings",
        items=items,
        on_back=lambda: None,
        dirty_tracker=is_dirty,
        mark_dirty=mark_dirty,
    )
