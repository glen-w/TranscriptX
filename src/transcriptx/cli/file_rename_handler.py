"""
File rename handler module for interactive file renaming.

This module provides reusable functions for renaming files with validation
and error handling.
"""

from pathlib import Path
from typing import Optional, Tuple

import questionary
from rich.console import Console

console = Console()


def validate_filename(name: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a filename for invalid characters.

    Args:
        name: The filename to validate

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is None.
    """
    if not name or not name.strip():
        return False, "Filename cannot be empty"

    # Check for invalid filesystem characters
    invalid_chars = ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
    found_invalid = [char for char in invalid_chars if char in name]

    if found_invalid:
        return False, f"Invalid characters in name: {', '.join(found_invalid)}"

    return True, None


def perform_rename(old_path: Path, new_name: str) -> Tuple[bool, Optional[Path]]:
    """
    Perform the actual file rename operation.

    Args:
        old_path: Current path to the file
        new_name: New filename (without path). If extension is not included,
                  the original file's extension will be preserved.

    Returns:
        Tuple of (success, new_path). If successful, new_path is the new Path.
        If failed, new_path is None.
    """
    if not old_path.exists():
        console.print(f"[red]❌ File does not exist: {old_path}[/red]")
        return False, None

    # Preserve original extension if user didn't include one
    original_extension = old_path.suffix
    if original_extension:
        # Strip trailing dots from user input (e.g., "file." -> "file")
        new_name = new_name.rstrip(".")
        # Check if new_name already has an extension
        new_name_path = Path(new_name)
        if not new_name_path.suffix:
            # No extension in new name, preserve original
            new_name = f"{new_name}{original_extension}"

    new_path = old_path.parent / new_name

    # Check if new name already exists (and it's not the same file)
    if new_path.exists() and new_path != old_path:
        console.print(f"[red]❌ File already exists: {new_name}[/red]")
        return False, None

    try:
        old_path.rename(new_path)
        console.print(f"[green]✅ Renamed: {old_path.name} -> {new_name}[/green]")
        return True, new_path
    except Exception as e:
        console.print(f"[red]❌ Error renaming file: {e}[/red]")
        return False, None


def rename_file_interactive(
    file_path: Path,
    current_name: Optional[str] = None,
    default_name: Optional[str] = None,
) -> Optional[str]:
    """
    Prompt user for a new filename and perform rename if valid.

    Args:
        file_path: Path to the file to rename
        current_name: Current filename (defaults to file_path.name)
        default_name: Default name to prefill in the prompt (defaults to current_name)

    Returns:
        New filename if rename was successful, None if cancelled or failed.
    """
    # Pause spinner for interactive workflow
    from transcriptx.utils.spinner import SpinnerManager

    SpinnerManager.pause_spinner()
    try:
        if current_name is None:
            current_name = file_path.name

        if default_name is None:
            default_name = current_name

        try:
            new_name = questionary.text(
                f"Enter new name for '{current_name}' (or press Enter to cancel):",
                default=default_name,
            ).ask()
        except KeyboardInterrupt:
            return None

        if not new_name or not new_name.strip():
            return None

        new_name = new_name.strip()

        # Don't rename if name hasn't changed
        if new_name == current_name:
            return None

        # Validate the new name
        is_valid, error_msg = validate_filename(new_name)
        if not is_valid:
            console.print(f"[red]❌ {error_msg}[/red]")
            return None

        # Perform the rename
        success, new_path = perform_rename(file_path, new_name)
        if success and new_path:
            return new_path.name

        return None
    finally:
        # Resume spinner after interactive workflow
        SpinnerManager.resume_spinner()
