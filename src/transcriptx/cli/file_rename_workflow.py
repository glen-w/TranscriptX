"""
File Rename Workflow Module for TranscriptX CLI.

This module provides a standalone tool for renaming files interactively.
Users can select a folder, browse files, and rename them using the centralized
file selection interface.

Key Features:
- Folder selection for file browsing
- File discovery and selection
- Interactive file renaming via centralized file_selection_interface
- Support for all file types
- Audio playback support for audio files

The rename functionality is centralized in file_selection_interface.py.
Users press 'r' on any file to rename it while browsing.
"""

from pathlib import Path
from typing import List, Optional

from rich import print

from transcriptx.cli.file_selection_interface import (
    FileSelectionConfig,
    select_files_interactive,
    _is_audio_file,
)
from transcriptx.core.utils.config import get_config
from transcriptx.cli.file_selection_utils import select_folder_interactive
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.utils.error_handling import graceful_exit

logger = get_logger()


def run_file_rename_workflow() -> None:
    """
    Run the file rename workflow main entry point.

    This function orchestrates the entire file renaming process:
    1. Folder selection
    2. File discovery
    3. Interactive browsing and renaming (via centralized file_selection_interface)

    Renaming is handled by the file_selection_interface module - users press 'r'
    on any file to rename it while browsing.
    """
    with graceful_exit():
        _run_file_rename_workflow_impl()


def _run_file_rename_workflow_impl() -> None:
    """Internal implementation of the file rename workflow."""
    try:
        print("\n[bold cyan]📝 Rename Files[/bold cyan]")
        print("[dim]Select files and rename them interactively[/dim]")

        # Step 1: Select folder location
        print("\n[bold]Step 1: Select folder containing files to rename[/bold]")

        # Use default start path based on platform
        import platform

        if platform.system() == "Darwin":
            default_start = Path("/Volumes/")
        else:
            from transcriptx.core.utils.paths import RECORDINGS_DIR

            default_start = Path(RECORDINGS_DIR)

        folder_path = select_folder_interactive(start_path=default_start)
        if not folder_path:
            print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
            return

        # Step 2: Discover all files in folder
        print(f"\n[bold]Step 2: Discovering files in {folder_path}[/bold]")
        all_files = _discover_all_files(folder_path)

        if not all_files:
            print(f"\n[yellow]⚠️ No files found in {folder_path}[/yellow]")
            return

        print(f"[green]✅ Found {len(all_files)} file(s)[/green]")

        # Step 3: Browse and rename files
        print("\n[bold]Step 3: Browse and rename files[/bold]")
        print(
            "[dim]Use arrow keys to navigate, [r] to rename, [→] to play audio, Enter when done[/dim]"
        )

        # Check if any files are audio files (enable playback if so)
        are_audio_files = any(_is_audio_file(f) for f in all_files)

        # Configure file selection interface with rename enabled
        # This uses the centralized rename functionality from file_selection_interface
        config = get_config()
        selection_config = FileSelectionConfig(
            multi_select=True,
            enable_playback=are_audio_files,  # Enable playback for audio files
            enable_rename=True,  # Enable built-in rename functionality (press 'r' to rename)
            enable_select_all=True,  # Allow selecting all files at once
            title="Rename Files (Press [r] to rename, [→] to play audio)",
            current_path=folder_path,
            skip_seconds_short=config.input.playback_skip_seconds_short,
            skip_seconds_long=config.input.playback_skip_seconds_long,
        )

        # The file selection interface handles renaming interactively
        # Users can press 'r' on any file to rename it while browsing
        selected_files = select_files_interactive(all_files, selection_config)

        if selected_files:
            print(
                f"\n[green]✅ Completed. Selected {len(selected_files)} file(s)[/green]"
            )
        else:
            print("\n[cyan]No files selected. Returning to menu.[/cyan]")

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
    except Exception as e:
        log_error(
            "FILE_RENAME_WORKFLOW",
            f"Error in file rename workflow: {e}",
            exception=e,
        )
        print(f"[red]❌ Error: {e}[/red]")


def _discover_all_files(folder_path: Path) -> List[Path]:
    """
    Discover all files in the given folder (non-recursive).

    Args:
        folder_path: Path to the folder to scan

    Returns:
        List of Path objects for all files found
    """
    files = []

    try:
        # Get all files in the folder (non-recursive)
        for item in folder_path.iterdir():
            if item.is_file():
                files.append(item)

        # Sort files by name for consistent display
        files.sort(key=lambda p: p.name.lower())

    except PermissionError:
        logger.warning(f"Permission denied accessing folder: {folder_path}")
        print(f"[red]❌ Permission denied accessing folder: {folder_path}[/red]")
    except Exception as e:
        log_error(
            "FILE_RENAME_WORKFLOW",
            f"Error discovering files in {folder_path}: {e}",
            exception=e,
        )
        print(f"[red]❌ Error discovering files: {e}[/red]")

    return files


def run_file_rename_non_interactive(
    folder: Path,
    files: Optional[List[Path]] = None,
    skip_confirm: bool = False,
) -> dict:
    """
    Run file rename workflow in non-interactive mode.

    Args:
        folder: Path to folder containing files to rename
        files: Optional list of specific files to rename (if None, all files in folder)
        skip_confirm: Skip confirmation prompts

    Returns:
        Dictionary with status and results
    """
    try:
        if not folder.exists():
            return {
                "status": "failed",
                "error": f"Folder does not exist: {folder}",
            }

        # Discover files if not provided
        if files is None:
            all_files = _discover_all_files(folder)
        else:
            # Validate provided files exist
            all_files = [f for f in files if f.exists()]
            if len(all_files) != len(files):
                missing = [f for f in files if not f.exists()]
                return {
                    "status": "failed",
                    "error": f"Some files do not exist: {missing}",
                }

        if not all_files:
            return {
                "status": "failed",
                "error": "No files found to rename",
            }

        # In non-interactive mode, we can't rename without new names
        # This function would need additional parameters for new names
        return {
            "status": "failed",
            "error": "Non-interactive rename requires new names to be provided",
        }

    except Exception as e:
        log_error(
            "FILE_RENAME_WORKFLOW",
            f"Error in non-interactive file rename: {e}",
            exception=e,
        )
        return {
            "status": "failed",
            "error": str(e),
        }
