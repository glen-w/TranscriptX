"""
Generic file selection interface with support for playback, rename, and metadata display.

This module provides a unified, configurable file selection interface that can be used
throughout the CLI for consistent UX.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Callable, Tuple

from prompt_toolkit import Application
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    HSplit,
    Window,
    FormattedTextControl,
    Layout,
)
from prompt_toolkit.widgets import CheckboxList
from rich.console import Console
import questionary

from transcriptx.cli.file_rename_handler import rename_file_interactive
from transcriptx.cli.audio_playback_handler import PlaybackController
from transcriptx.cli.file_metadata_formatters import (
    format_audio_file,
    format_audio_file_fast,
    format_transcript_file,
    format_readable_transcript_file,
    format_generic_file,
    is_audio_file,
)

# Re-export for backward compatibility (used by other modules)
# Keep _is_audio_file alias for backward compatibility
_is_audio_file = is_audio_file
from transcriptx.cli.file_selection_ui_helpers import build_help_text, build_header_text
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger, log_error

logger = get_logger()
console = Console()


@dataclass
class FileSelectionConfig:
    """Configuration for file selection interface."""

    # Selection mode
    multi_select: bool = True

    # Optional features
    enable_playback: bool = False
    enable_rename: bool = False
    enable_select_all: bool = False
    auto_exit_when_one_remains: bool = (
        False  # Auto-exit when only one file remains (useful for duplicate groups)
    )

    # UI customization
    title: str = "File Selection"
    current_path: Optional[Path] = None
    metadata_formatter: Optional[Callable[[Path], str]] = None

    # File validation
    validator: Optional[Callable[[Path], Tuple[bool, Optional[str]]]] = None

    # Optional toggle to include hidden files (e.g., already-transcribed)
    toggle_hidden_files: Optional[List[Path]] = None
    toggle_hidden_label: str = "Show transcribed"
    toggle_hidden_key: str = "t"


# Re-export formatter functions for backward compatibility
# These are now implemented in file_metadata_formatters module
__all__ = [
    "FileSelectionConfig",
    "select_files_interactive",
    "format_audio_file",
    "format_audio_file_fast",
    "format_transcript_file",
    "format_readable_transcript_file",
    "format_generic_file",
    "is_audio_file",
]


def select_files_interactive(
    files: List[Path], config: FileSelectionConfig
) -> Optional[List[Path]]:
    """
    Interactive file selection with optional playback and rename support.

    Args:
        files: List of file paths to select from
        config: Configuration for the selection interface

    Returns:
        List of selected file paths, or None if cancelled. For single-select mode,
        returns a list with one item or None.
    """
    if not files:
        console.print("[yellow]⚠️ No files available for selection[/yellow]")
        return None

    # Auto-detect audio files and enable playback if not explicitly set
    # Only auto-enable if all files are audio files
    if all(is_audio_file(f) for f in files):
        config.enable_playback = True

    # Default formatter if not provided
    if config.metadata_formatter is None:
        if all(is_audio_file(f) for f in files):
            config.metadata_formatter = format_audio_file
        else:
            config.metadata_formatter = format_generic_file

    full_metadata_formatter = config.metadata_formatter
    use_fast_audio_metadata = full_metadata_formatter == format_audio_file

    # Initialize playback controller if needed
    playback_controller = None
    if config.enable_playback:
        playback_controller = PlaybackController()

    # Track hidden file toggle state
    base_files = list(files)
    hidden_files = list(config.toggle_hidden_files or [])
    hidden_files = [f for f in hidden_files if f not in base_files]
    show_hidden = False

    def get_visible_files() -> List[Path]:
        if show_hidden and hidden_files:
            return base_files + hidden_files
        return base_files

    files = get_visible_files()

    # Cache file metadata on first load to avoid expensive disk I/O during UI updates
    # This is critical for performance, especially on USB drives
    # Load metadata once and cache it forever - prevents re-reading file stats and audio duration
    file_metadata_cache: dict[Path, dict] = {}
    original_labels: dict[Path, str] = {}
    all_files = files + [f for f in hidden_files if f not in files]
    initial_formatter = (
        format_audio_file_fast if use_fast_audio_metadata else full_metadata_formatter
    )
    for file_path in all_files:
        try:
            label = initial_formatter(file_path)
            # Store the formatted label in cache
            file_metadata_cache[file_path] = {"label": label}
            original_labels[file_path] = label
        except Exception as e:
            # Fallback if metadata loading fails
            label = f"📄 {file_path.name}"
            file_metadata_cache[file_path] = {"label": label}
            original_labels[file_path] = label
            logger.debug(f"Failed to load metadata for {file_path}: {e}")

    # Create choices for checkbox list using cached labels
    choices: List[Tuple[Path, str]] = []
    for file_path in files:
        label = original_labels.get(file_path, f"📄 {file_path.name}")
        choices.append((file_path, label))

    # Add "Select All" option if enabled
    select_all_value = object()  # Unique object to identify "Select All"
    if config.enable_select_all and config.multi_select:
        choices.insert(0, (select_all_value, "✅ Select All"))

    # Create checkbox list
    checkbox_list = CheckboxList(values=choices)

    # Track currently playing file for UI updates
    currently_playing_file: Optional[Path] = None

    # Track reverse order state
    is_reversed: bool = False

    # Helper function to rebuild choices with updated labels
    def rebuild_choices() -> List[Tuple[Path, str]]:
        """
        Rebuild choices list with updated labels based on playback state.

        Uses cached metadata to avoid expensive disk I/O operations.
        This is critical for performance, especially on USB drives.
        """
        new_choices: List[Tuple[Path, str]] = []
        for file_path in files:
            # Always use original label from cache (without play icon)
            # This ensures icons are properly removed when playback stops or switches
            cached = file_metadata_cache.get(file_path)
            if cached:
                label = cached["label"]
            else:
                # Fallback to original_labels (shouldn't happen if cache was populated correctly)
                label = original_labels.get(file_path, f"📄 {file_path.name}")

            # Strip any existing play icon to ensure clean state
            if label.startswith("▶️ "):
                label = label[2:]  # Remove "▶️ " prefix

            # Add play indicator only to currently playing file
            if currently_playing_file and file_path == currently_playing_file:
                label = f"▶️ {label}"

            new_choices.append((file_path, label))

        # Add "Select All" option if enabled
        if config.enable_select_all and config.multi_select:
            new_choices.insert(0, (select_all_value, "✅ Select All"))

        return new_choices

    def rebuild_header_text() -> FormattedText:
        return build_header_text(
            title=config.title,
            current_path=str(config.current_path) if config.current_path else None,
            file_count=len(files),
        )

    # Create key bindings
    kb = KeyBindings()

    # Add playback key bindings if enabled
    if config.enable_playback and playback_controller:

        def get_current_file() -> Optional[Path]:
            """Get the currently highlighted file."""
            try:
                idx = getattr(checkbox_list, "_selected_index", 0)
                if isinstance(idx, int) and 0 <= idx < len(choices):
                    choice_value, _ = choices[idx]
                    if choice_value is not select_all_value and isinstance(
                        choice_value, Path
                    ):
                        return choice_value
            except (IndexError, AttributeError, TypeError):
                pass
            return None

        # Add playback key bindings directly
        @kb.add("right")
        def play_current_file(event):
            nonlocal currently_playing_file, choices
            file_path = get_current_file()
            if file_path:
                # Preserve current selection index and file path before updating UI
                try:
                    current_index = getattr(checkbox_list, "_selected_index", 0)
                except (AttributeError, TypeError):
                    current_index = 0

                if playback_controller.play(file_path):
                    # Update currently playing file
                    currently_playing_file = file_path
                    # Update UI in-place without exiting app
                    # This is much faster than recreating the entire application
                    choices = rebuild_choices()
                    checkbox_list.values = choices

                    # Restore selection index to preserve navigation position
                    # Try to restore by index first, then fall back to finding by file path
                    try:
                        if isinstance(current_index, int) and 0 <= current_index < len(
                            choices
                        ):
                            checkbox_list._selected_index = current_index
                        else:
                            # Fallback: find the file by path in the new choices
                            for idx, (value, _) in enumerate(choices):
                                if value == file_path:
                                    checkbox_list._selected_index = idx
                                    break
                    except (AttributeError, TypeError):
                        # If we can't set the index, try to find the file by path
                        try:
                            for idx, (value, _) in enumerate(choices):
                                if value == file_path:
                                    checkbox_list._selected_index = idx
                                    break
                        except (AttributeError, TypeError):
                            pass

                    event.app.invalidate()  # Trigger redraw

        @kb.add("left")
        def stop_playback(event):
            nonlocal currently_playing_file, choices
            # Preserve current selection index and file path before updating UI
            try:
                current_index = getattr(checkbox_list, "_selected_index", 0)
                # Also get the current file path as a fallback
                if isinstance(current_index, int) and 0 <= current_index < len(choices):
                    current_file_path = (
                        choices[current_index][0]
                        if choices[current_index][0] is not select_all_value
                        else None
                    )
                else:
                    current_file_path = None
            except (AttributeError, TypeError, IndexError):
                current_index = 0
                current_file_path = None

            playback_controller.stop()
            # Update UI to remove "Playing:" status
            currently_playing_file = None
            # Update UI in-place without exiting app
            choices = rebuild_choices()
            checkbox_list.values = choices

            # Restore selection index to preserve navigation position
            # Try to restore by index first, then fall back to finding by file path
            try:
                if isinstance(current_index, int) and 0 <= current_index < len(choices):
                    checkbox_list._selected_index = current_index
                elif current_file_path:
                    # Fallback: find the file by path in the new choices
                    for idx, (value, _) in enumerate(choices):
                        if value == current_file_path:
                            checkbox_list._selected_index = idx
                            break
            except (AttributeError, TypeError):
                # If we can't set the index, try to find the file by path
                if current_file_path:
                    try:
                        for idx, (value, _) in enumerate(choices):
                            if value == current_file_path:
                                checkbox_list._selected_index = idx
                                break
                    except (AttributeError, TypeError):
                        pass

            event.app.invalidate()  # Trigger redraw
            # Don't print to console - it interferes with prompt_toolkit UI navigation

        @kb.add(",", eager=True)
        @kb.add("<", eager=True)
        def skip_backward(event):
            playback_controller.skip(-10.0)

        @kb.add(".", eager=True)
        @kb.add(">", eager=True)
        def skip_forward(event):
            playback_controller.skip(10.0)

    # Add rename key binding if enabled
    if config.enable_rename:

        @kb.add("r", eager=True)
        def rename_current_file(event):
            """Rename the currently highlighted file when 'r' is pressed."""
            try:
                idx = getattr(checkbox_list, "_selected_index", 0)
                if not isinstance(idx, int) or idx < 0 or idx >= len(choices):
                    return

                choice_value, _ = choices[idx]
                if choice_value is select_all_value:
                    return

                if isinstance(choice_value, Path):
                    # Force exit with rename result
                    event.app.exit(result="__RENAME__" + str(idx))
                    return
            except (IndexError, AttributeError, TypeError) as e:
                logger.debug(f"Error in rename handler: {e}")
                pass

    # Add jump navigation key bindings
    @kb.add("pagedown")
    @kb.add("s-down")  # Shift+Down as alternative
    def jump_down_10(event):
        """Jump down 10 items when Page Down or Shift+Down is pressed."""
        try:
            current_index = getattr(checkbox_list, "_selected_index", 0)
            if not isinstance(current_index, int):
                current_index = 0
            max_index = len(choices) - 1
            new_index = min(current_index + 10, max_index)
            checkbox_list._selected_index = new_index
            event.app.invalidate()
        except (AttributeError, TypeError, IndexError):
            pass

    @kb.add("pageup")
    @kb.add("s-up")  # Shift+Up as alternative
    def jump_up_10(event):
        """Jump up 10 items when Page Up or Shift+Up is pressed."""
        try:
            current_index = getattr(checkbox_list, "_selected_index", 0)
            if not isinstance(current_index, int):
                current_index = 0
            new_index = max(current_index - 10, 0)
            checkbox_list._selected_index = new_index
            event.app.invalidate()
        except (AttributeError, TypeError, IndexError):
            pass

    # Add reverse order key binding
    @kb.add("o", eager=True)
    def reverse_order(event):
        """Reverse the order of files when 'o' is pressed."""
        nonlocal files, choices, is_reversed
        try:
            # Get current selection index to preserve position
            try:
                current_index = getattr(checkbox_list, "_selected_index", 0)
                # Get the current file path if possible
                if isinstance(current_index, int) and 0 <= current_index < len(choices):
                    current_choice_value = choices[current_index][0]
                    current_file_path = (
                        current_choice_value
                        if isinstance(current_choice_value, Path)
                        and current_choice_value is not select_all_value
                        else None
                    )
                else:
                    current_file_path = None
            except (AttributeError, TypeError, IndexError):
                current_file_path = None

            # Reverse the files list
            files.reverse()
            is_reversed = not is_reversed

            # Rebuild choices with reversed order
            choices = rebuild_choices()
            checkbox_list.values = choices

            # Restore selection to the same file (if it exists)
            if current_file_path:
                try:
                    for idx, (value, _) in enumerate(choices):
                        if value == current_file_path:
                            checkbox_list._selected_index = idx
                            break
                except (AttributeError, TypeError):
                    pass

            event.app.invalidate()  # Trigger redraw
        except Exception as e:
            logger.debug(f"Error in reverse_order handler: {e}")

    # Add toggle hidden files key binding
    if hidden_files:

        @kb.add(config.toggle_hidden_key, eager=True)
        def toggle_hidden_files(event):
            """Toggle visibility of hidden files (e.g., already transcribed)."""
            nonlocal files, choices, show_hidden
            try:
                # Preserve current selection index and file path
                try:
                    current_index = getattr(checkbox_list, "_selected_index", 0)
                    if isinstance(current_index, int) and 0 <= current_index < len(
                        choices
                    ):
                        current_choice_value = choices[current_index][0]
                        current_file_path = (
                            current_choice_value
                            if isinstance(current_choice_value, Path)
                            and current_choice_value is not select_all_value
                            else None
                        )
                    else:
                        current_file_path = None
                except (AttributeError, TypeError, IndexError):
                    current_index = 0
                    current_file_path = None

                # Preserve selected values
                selected_values: list[Path] = []
                try:
                    selected_indices = getattr(checkbox_list, "_selected_rows", set())
                    if selected_indices:
                        # _selected_rows is a set; sort for deterministic ordering.
                        for i in sorted(selected_indices):
                            if i < len(choices):
                                value = choices[i][0]
                                if isinstance(value, Path):
                                    selected_values.append(value)
                except (AttributeError, TypeError, IndexError):
                    if hasattr(checkbox_list, "current_values"):
                        selected_values = [
                            v
                            for v in list(checkbox_list.current_values)
                            if isinstance(v, Path)
                        ]

                # Toggle visibility
                show_hidden = not show_hidden
                files = get_visible_files()

                # Rebuild UI
                choices = rebuild_choices()
                checkbox_list.values = choices

                # Restore selected values
                try:
                    value_to_index = {value: idx for idx, (value, _) in enumerate(choices)}
                    new_selected_rows = {
                        value_to_index[value]
                        for value in selected_values
                        if value in value_to_index
                    }
                    if hasattr(checkbox_list, "_selected_rows"):
                        checkbox_list._selected_rows = new_selected_rows
                except (AttributeError, TypeError):
                    pass

                # Restore selection to the same file if possible
                if current_file_path:
                    try:
                        for idx, (value, _) in enumerate(choices):
                            if value == current_file_path:
                                checkbox_list._selected_index = idx
                                break
                    except (AttributeError, TypeError):
                        pass
                elif isinstance(current_index, int) and current_index < len(choices):
                    checkbox_list._selected_index = current_index

                # Update header
                header_control.text = rebuild_header_text()

                event.app.invalidate()
            except Exception as e:
                logger.debug(f"Error in toggle_hidden_files handler: {e}")

    # Add delete key binding
    @kb.add("delete", eager=True)
    @kb.add("c-d", eager=True)
    def delete_current_file(event):
        """Delete the currently highlighted file when Delete or Ctrl+D is pressed."""
        try:
            idx = getattr(checkbox_list, "_selected_index", 0)
            if not isinstance(idx, int) or idx < 0 or idx >= len(choices):
                return

            choice_value, _ = choices[idx]
            if choice_value is select_all_value:
                return

            if isinstance(choice_value, Path):
                event.app.exit(result="__DELETE__" + str(idx))
        except (IndexError, AttributeError, TypeError):
            pass

    @kb.add("c-c")
    @kb.add("escape")
    def exit_app(event):
        """Exit on Ctrl+C or Escape (cancel)."""
        if playback_controller:
            playback_controller.stop()
        event.app.exit(result=None)

    # In single-select mode, Enter confirms the highlighted item
    if not config.multi_select:

        @kb.add("enter", eager=True)
        @kb.add("c-m", eager=True)  # Enter (control-m on some terminals)
        def confirm_highlighted(event):
            """Confirm the highlighted file when Enter is pressed (single-select)."""
            try:
                idx = getattr(checkbox_list, "_selected_index", 0)
                if isinstance(idx, int) and 0 <= idx < len(choices):
                    value = choices[idx][0]
                    if value is not select_all_value and isinstance(value, Path):
                        event.app.exit(result=[value])
            except (AttributeError, TypeError, IndexError):
                pass

    @kb.add("f", eager=True)
    def confirm_selection(event):
        """Confirm selection when 'f' (finish) is pressed if items are selected, otherwise do nothing."""
        try:
            # Prefer _selected_rows as it's more reliable for getting actual selected items
            selected_values = []
            try:
                selected_indices = getattr(checkbox_list, "_selected_rows", set())
                if selected_indices:
                    # _selected_rows is a set; sort for deterministic ordering.
                    selected_values = [
                        choices[i][0]
                        for i in sorted(selected_indices)
                        if i < len(choices)
                    ]
            except (AttributeError, IndexError, TypeError):
                pass

            # Fallback to current_values if _selected_rows doesn't work
            if not selected_values:
                selected_values = (
                    list(checkbox_list.current_values)
                    if hasattr(checkbox_list, "current_values")
                    else []
                )

            # Check if "Select All" is selected
            select_all_selected = select_all_value in selected_values

            # Filter out "Select All" and get actual selected files
            actual_selected_files = [
                v
                for v in selected_values
                if v is not select_all_value and isinstance(v, Path)
            ]

            # If "Select All" is selected or there are actual selected files, confirm and exit
            if select_all_selected or len(actual_selected_files) > 0:
                # If "Select All" is selected, include it so the handler below processes it correctly
                # Otherwise, only return the actually selected files (not all files)
                if select_all_selected:
                    result_values = selected_values.copy()
                else:
                    # Only return the actually selected files, not all files
                    result_values = actual_selected_files.copy()
                # Force exit with result
                event.app.exit(result=result_values)
                return
            # If no items are selected, 'f' does nothing (use Space to toggle)
            # This prevents 'f' from toggling when user wants to confirm
        except (AttributeError, Exception) as e:
            # If we can't get selected rows, exit with empty list
            logger.debug(f"Error in confirm handler: {e}")
            event.app.exit(result=[])

    # In multi-select mode, Enter should also confirm (common expectation).
    if config.multi_select:

        @kb.add("enter", eager=True)
        @kb.add("c-m", eager=True)  # Enter (control-m on some terminals)
        def confirm_selection_enter(event):
            confirm_selection(event)

    # Build help text with keyboard shortcuts
    shortcuts = [
        ("☑️", "Select", "[Space]"),
        ("↕️", "Navigate", "[↑↓]"),
        ("⏬", "Jump +10", "[PgDn/Shift+↓]"),
        ("⏫", "Jump -10", "[PgUp/Shift+↑]"),
        ("🔄", "Reverse", "[o]"),
    ]
    if config.enable_playback:
        shortcuts.extend(
            [
                ("▶️", "Play", "[→]"),
                ("⏸️", "Stop", "[←]"),
                ("⏪", "Skip -10s", "[,/<]"),
                ("⏩", "Skip +10s", "[./>]"),
            ]
        )
    if config.enable_rename:
        shortcuts.append(("✏️", "Rename", "[r]"))
    if hidden_files:
        shortcuts.append(
            ("👁️", config.toggle_hidden_label, f"[{config.toggle_hidden_key}]")
        )
    confirm_key = "[Enter/f]"
    shortcuts.extend(
        [
            ("🗑️", "Delete", "[Delete/Ctrl+D]"),
            ("✅", "Confirm", confirm_key),
            ("❌", "Cancel", "[Esc/Ctrl+C]"),
        ]
    )

    help_text = build_help_text(shortcuts, box_width=None)
    help_height = ((len(shortcuts) + 1) // 2) + 2  # rows + top/bottom border
    header_text = build_header_text(
        title=config.title,
        current_path=str(config.current_path) if config.current_path else None,
        file_count=len(files),
    )
    header_control = FormattedTextControl(text=header_text)
    header_window = Window(header_control, height=4)

    layout = Layout(
        HSplit(
            [
                header_window,
                checkbox_list,
                Window(help_text, height=help_height),
            ]
        )
    )

    async def refresh_full_metadata(app: Application) -> None:
        """Load full metadata in the background and refresh labels."""
        def load_full_labels() -> dict[Path, str]:
            updated_labels: dict[Path, str] = {}
            for file_path in all_files:
                try:
                    updated_labels[file_path] = full_metadata_formatter(file_path)
                except Exception as e:
                    updated_labels[file_path] = f"📄 {file_path.name}"
                    logger.debug(
                        f"Failed to load metadata for {file_path}: {e}"
                    )
            return updated_labels

        updated_labels = await asyncio.to_thread(load_full_labels)
        for file_path, label in updated_labels.items():
            file_metadata_cache[file_path] = {"label": label}
            original_labels[file_path] = label

        nonlocal choices
        choices = rebuild_choices()
        checkbox_list.values = choices
        app.invalidate()

    metadata_task_started = False

    def before_render(app: Application) -> None:
        nonlocal metadata_task_started
        if use_fast_audio_metadata and not metadata_task_started:
            metadata_task_started = True
            app.create_background_task(refresh_full_metadata(app))

    # Create application with our key bindings
    # Note: We set key_bindings here to ensure they take precedence
    app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=False,
        erase_when_done=False,
        before_render=before_render,
    )

    # Run application in a loop to handle rename requests
    try:
        while True:
            try:
                result = app.run()
            except (OSError, ValueError, KeyError) as e:
                # These errors often occur due to terminal/event loop conflicts
                # Log the error and provide a fallback
                logger.error(f"Error running prompt_toolkit application (terminal conflict?): {e}", exc_info=True)
                if playback_controller:
                    playback_controller.stop()
                # Return None to trigger fallback in calling code
                console.print("[yellow]⚠️ Interactive menu unavailable. Using fallback selection...[/yellow]")
                return None
            except Exception as e:
                # Log other errors for debugging
                logger.error(f"Unexpected error running prompt_toolkit application: {e}", exc_info=True)
                if playback_controller:
                    playback_controller.stop()
                # Re-raise to be caught by outer exception handler
                raise
            
            if result is None:
                if playback_controller:
                    playback_controller.stop()
                return None

            # Handle rename request
            if isinstance(result, str) and result.startswith("__RENAME__"):
                try:
                    idx = int(result.replace("__RENAME__", ""))
                    if 0 <= idx < len(choices):
                        choice_value, _ = choices[idx]
                        if choice_value is not select_all_value and isinstance(
                            choice_value, Path
                        ):
                            file_path = choice_value
                            old_name = file_path.name

                            default_name = old_name
                            if get_config().input.prefill_rename_with_date_prefix:
                                # Extract YYMMDD from filename to prefill rename field
                                from transcriptx.core.utils.file_rename import (
                                    extract_date_prefix_from_filename,
                                )

                                date_prefix = extract_date_prefix_from_filename(old_name)
                                default_name = date_prefix if date_prefix else old_name

                            # Perform rename
                            new_name = rename_file_interactive(
                                file_path, old_name, default_name=default_name
                            )

                            if new_name and new_name != old_name:
                                # Update files list
                                try:
                                    file_idx = files.index(file_path)
                                    new_path = file_path.parent / new_name
                                    files[file_idx] = new_path

                                    # Update metadata cache and original_labels for renamed file
                                    if file_path in file_metadata_cache:
                                        # Load new metadata for renamed file
                                        try:
                                            new_label = config.metadata_formatter(
                                                new_path
                                            )
                                            file_metadata_cache[new_path] = {
                                                "label": new_label
                                            }
                                            original_labels[new_path] = new_label
                                        except Exception as e:
                                            # Fallback if metadata loading fails
                                            new_label = f"📄 {new_path.name}"
                                            file_metadata_cache[new_path] = {
                                                "label": new_label
                                            }
                                            original_labels[new_path] = new_label
                                            logger.debug(
                                                f"Failed to load metadata for renamed file {new_path}: {e}"
                                            )
                                        # Remove old cache entry
                                        del file_metadata_cache[file_path]
                                        if file_path in original_labels:
                                            del original_labels[file_path]

                                    # Update currently_playing_file if this was the playing file
                                    if currently_playing_file == file_path:
                                        currently_playing_file = new_path

                                    # Rebuild choices with updated file info
                                    choices = rebuild_choices()

                                    # Recreate checkbox list
                                    checkbox_list = CheckboxList(values=choices)

                                    # Update layout
                                    layout = Layout(
                                        HSplit(
                                            [
                                                Window(
                                                    FormattedTextControl(
                                                        text=header_text
                                                    ),
                                                    height=4,
                                                ),
                                                checkbox_list,
                                                Window(help_text, height=7),
                                            ]
                                        )
                                    )

                                    # Recreate app
                                    app = Application(
                                        layout=layout,
                                        key_bindings=kb,
                                        full_screen=False,
                                        before_render=before_render,
                                    )

                                    continue
                                except (ValueError, Exception) as e:
                                    console.print(
                                        f"[yellow]⚠️ Could not update file list: {e}[/yellow]"
                                    )
                                    continue
                            # If rename was cancelled or failed, continue loop
                            continue
                except (ValueError, IndexError, AttributeError):
                    return None

            # Handle delete request
            if isinstance(result, str) and result.startswith("__DELETE__"):
                try:
                    idx = int(result.replace("__DELETE__", ""))
                    if 0 <= idx < len(choices):
                        choice_value, _ = choices[idx]
                        if choice_value is select_all_value:
                            continue

                        if isinstance(choice_value, Path):
                            file_path = choice_value

                            # Confirm deletion
                            confirm = questionary.confirm(
                                f"Delete file '{file_path.name}'?", default=False
                            ).ask()

                            if confirm:
                                try:
                                    # Stop playback if this file is playing
                                    if (
                                        playback_controller
                                        and playback_controller._current_file
                                        == file_path
                                    ):
                                        playback_controller.stop()
                                        currently_playing_file = None

                                    # Delete the file
                                    file_path.unlink()
                                    console.print(
                                        f"[green]✓ Deleted {file_path.name}[/green]"
                                    )

                                    # Remove from files list
                                    if file_path in files:
                                        files.remove(file_path)

                                    # Remove from metadata cache and original_labels
                                    if file_path in file_metadata_cache:
                                        del file_metadata_cache[file_path]
                                    if file_path in original_labels:
                                        del original_labels[file_path]

                                    # Rebuild choices with updated file info
                                    choices = rebuild_choices()

                                    # Update header with new file count
                                    header_text = build_header_text(
                                        title=config.title,
                                        current_path=(
                                            str(config.current_path)
                                            if config.current_path
                                            else None
                                        ),
                                        file_count=len(files),
                                    )

                                    # Recreate checkbox list
                                    checkbox_list = CheckboxList(values=choices)

                                    # Update layout
                                    layout = Layout(
                                        HSplit(
                                            [
                                                Window(
                                                    FormattedTextControl(
                                                        text=header_text
                                                    ),
                                                    height=4,
                                                ),
                                                checkbox_list,
                                                Window(help_text, height=7),
                                            ]
                                        )
                                    )

                                    # Recreate app
                                    app = Application(
                                        layout=layout,
                                        key_bindings=kb,
                                        full_screen=False,
                                        before_render=before_render,
                                    )

                                    # If no files left, exit
                                    if not files:
                                        console.print(
                                            "[yellow]⚠️ No files remaining[/yellow]"
                                        )
                                        if playback_controller:
                                            playback_controller.stop()
                                        return None

                                    # If only one file remains and auto-exit is enabled, exit automatically
                                    if (
                                        config.auto_exit_when_one_remains
                                        and len(files) == 1
                                    ):
                                        if playback_controller:
                                            playback_controller.stop()
                                        return None

                                    continue
                                except Exception as e:
                                    console.print(
                                        f"[red]❌ Error deleting file: {e}[/red]"
                                    )
                                    continue
                            # If deletion was cancelled, continue loop
                            continue
                except (ValueError, IndexError, AttributeError):
                    return None

            # Normal result processing
            break

        # Handle "Select All" option
        if select_all_value in result:
            selected_files = []
            for file_path in files:
                if config.validator:
                    is_valid, error_msg = config.validator(file_path)
                    if not is_valid:
                        console.print(
                            f"[yellow]⚠️ Invalid file {file_path.name}: {error_msg}[/yellow]"
                        )
                        continue
                selected_files.append(file_path)
            return selected_files if selected_files else None

        # Filter out "Select All" if present
        selected_files = []
        for value in result:
            if value is not select_all_value and isinstance(value, Path):
                if config.validator:
                    is_valid, error_msg = config.validator(value)
                    if not is_valid:
                        console.print(
                            f"[yellow]⚠️ Invalid file {value.name}: {error_msg}[/yellow]"
                        )
                        continue
                selected_files.append(value)

        if not config.multi_select:
            # Single-select mode: return first selected or None
            return [selected_files[0]] if selected_files else None

        return selected_files if selected_files else None

    except KeyboardInterrupt:
        if playback_controller:
            playback_controller.stop()
        console.print("\n[cyan]Cancelled. Returning to previous menu.[/cyan]")
        return None
    except Exception as e:
        if playback_controller:
            playback_controller.stop()
        error_msg = f"Error in file selection: {str(e)}"
        console.print(f"[red]❌ {error_msg}[/red]")
        log_error("FILE_SELECTION", error_msg, exception=e)
        return None
