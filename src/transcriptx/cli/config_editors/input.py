"""Input configuration editor."""

import questionary
from rich import print

from transcriptx.cli.settings import (
    SettingItem,
    create_bool_editor,
    create_choice_editor,
    settings_menu_loop,
)
from ._dirty_tracker import is_dirty, mark_dirty


def edit_input_config(config):
    """Edit input configuration."""

    def _edit_folder_list(title: str, current_list: list[str]) -> list[str] | None:
        print(f"\n[bold]{title}[/bold]")
        print(
            "[dim]You can configure up to 3 folders that will be tried in order.[/dim]"
        )
        print("[dim]Leave blank to skip/remove a slot.[/dim]")
        new_list: list[str] = []
        for slot_num in range(1, 4):
            current_value = (
                current_list[slot_num - 1] if len(current_list) >= slot_num else ""
            )
            value = questionary.text(
                f"Path for {title.lower()} {slot_num}",
                default=current_value,
            ).ask()
            if value is None:
                return None
            if value.strip():
                new_list.append(value.strip())
        return new_list

    def wav_folders_editor(_: SettingItem):
        current = config.input.wav_folders or []
        new_list = _edit_folder_list("WAV folder", current)
        if new_list is None:
            return None
        return new_list

    def recordings_folders_editor(_: SettingItem):
        current = config.input.recordings_folders or []
        new_list = _edit_folder_list("Recordings folder", current)
        if new_list is None:
            return None
        return new_list

    items = [
        SettingItem(
            order=1,
            key="input.wav_folders",
            label="WAV folders",
            getter=lambda: config.input.wav_folders,
            setter=lambda value: setattr(config.input, "wav_folders", value),
            editor=wav_folders_editor,
        ),
        SettingItem(
            order=2,
            key="input.recordings_folders",
            label="Recordings folders",
            getter=lambda: config.input.recordings_folders,
            setter=lambda value: setattr(config.input, "recordings_folders", value),
            editor=recordings_folders_editor,
        ),
        SettingItem(
            order=3,
            key="input.prefill_rename_with_date_prefix",
            label="Prefill rename with date prefix",
            getter=lambda: config.input.prefill_rename_with_date_prefix,
            setter=lambda value: setattr(
                config.input, "prefill_rename_with_date_prefix", value
            ),
            editor=create_bool_editor(
                hint="Controls whether rename inputs start with a date prefix."
            ),
        ),
        SettingItem(
            order=4,
            key="input.file_selection_mode",
            label="File selection preference",
            getter=lambda: getattr(config.input, "file_selection_mode", "prompt"),
            setter=lambda value: setattr(config.input, "file_selection_mode", value),
            editor=create_choice_editor(
                choices=["prompt", "explore", "direct"],
                hint="prompt = ask each time; explore = file browser by default; direct = type path by default.",
            ),
        ),
    ]

    settings_menu_loop(
        title="📥 Input Settings",
        items=items,
        on_back=lambda: None,
        dirty_tracker=is_dirty,
        mark_dirty=mark_dirty,
    )
