"""
Deduplication Workflow Module for TranscriptX CLI.

This module provides a standalone tool for finding and removing duplicate files
using a feature-rich file selection interface with playback, rename, and delete capabilities.

Key Features:
- Folder selection for duplicate scanning
- Discovery of all file types (not just WAV)
- Duplicate detection by file size
- Feature-rich file selection interface (playback, rename, delete)
- Group-by-group review of duplicates
"""

from pathlib import Path
from typing import List, Dict, Any
import os
import sys

import questionary
from rich import print

from transcriptx.cli.file_discovery import (
    find_duplicate_files_by_size,
    find_duplicate_files_by_size_and_content,
    _format_file_size,
)
from transcriptx.cli.file_selection_interface import (
    FileSelectionConfig,
    select_files_interactive,
    _is_audio_file,
)
from transcriptx.cli.audio import get_audio_duration
from transcriptx.cli.file_selection_utils import select_folder_interactive
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.utils.error_handling import graceful_exit

logger = get_logger()


def run_deduplication_workflow() -> None:
    """
    Run the deduplication workflow main entry point.

    This function orchestrates the entire deduplication process:
    1. Folder selection
    2. File discovery
    3. Duplicate detection
    4. Interactive review and deletion
    """
    with graceful_exit():
        _run_deduplication_workflow_impl()


def _run_deduplication_workflow_impl() -> None:
    """Internal implementation of the deduplication workflow."""
    try:
        print("\n[bold cyan]🔍 Find & Remove Duplicates[/bold cyan]")
        print(
            "[dim]Discover and remove duplicate files using size and audio content comparison[/dim]"
        )

        # Step 1: Select folder location
        print("\n[bold]Step 1: Select folder to scan for duplicates[/bold]")
        config = get_config()
        default_start = Path("/Volumes/")
        if hasattr(config.output, "default_audio_folder"):
            default_start = Path(
                getattr(config.output, "default_audio_folder", "/Volumes/")
            )

        folder_path = select_folder_interactive(start_path=default_start)
        if not folder_path:
            print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
            return

        # Step 2: Discover all files in folder
        print(f"\n[bold]Step 2: Discovering files in {folder_path}[/bold]")
        all_files = _discover_all_files(folder_path)

        if not all_files:
            print(f"\n[yellow]⚠️ No files found in {folder_path}[/yellow]")
            return

        print(f"[green]✅ Found {len(all_files)} file(s)[/green]")

        # Step 3: Find duplicate groups using two-pass detection
        print("\n[bold]Step 3: Checking for duplicate files...[/bold]")
        print("[dim]First pass: Grouping by file size...[/dim]")

        # Use content-based detection if available
        from transcriptx.cli.audio_fingerprinting import is_librosa_available
        from transcriptx.cli.main import _check_and_install_librosa

        # Lazy initialization: check and install librosa if needed
        if not is_librosa_available():
            _check_and_install_librosa(allow_install=True)

        if is_librosa_available():
            print(
                "[dim]Second pass: Comparing audio content for size-matched files...[/dim]"
            )
            duplicate_groups = find_duplicate_files_by_size_and_content(
                all_files,
                threshold=config.output.audio_deduplication_threshold,
                show_progress=True,
            )
        else:
            print(
                "[yellow]⚠️ librosa not available. Using size-only detection.[/yellow]"
            )
            print(
                "[dim]Install librosa for content-based duplicate detection: pip install librosa>=0.10.0[/dim]"
            )
            duplicate_groups = find_duplicate_files_by_size(all_files)

        if not duplicate_groups:
            print("\n[green]✅ No duplicate files found![/green]")
            print("[dim]All files are unique.[/dim]")
            return

        # Sort groups by size (largest first) for review
        sorted_groups = sorted(
            duplicate_groups.items(), key=lambda x: x[0], reverse=True
        )
        total_groups = len(sorted_groups)

        # Determine detection method for display
        detection_method = (
            "size and audio content" if is_librosa_available() else "file size"
        )
        print(
            f"\n[bold yellow]🔍 Found {total_groups} duplicate group(s) (matched by {detection_method})[/bold yellow]"
        )

        # Step 4: Review each duplicate group
        total_deleted = 0
        for group_idx, (size_bytes, duplicate_files) in enumerate(sorted_groups, 1):
            size_str = _format_file_size(size_bytes)
            num_files = len(duplicate_files)

            print(
                f"\n[bold cyan]Duplicate Group {group_idx} of {total_groups}[/bold cyan]"
            )
            print(
                f"[dim]Size: {size_str} ({size_bytes} bytes) | {num_files} file(s) with identical size[/dim]"
            )

            # Use feature-rich file selection interface
            deleted_from_group = _review_duplicate_group(
                duplicate_files, size_bytes, group_idx, total_groups, folder_path
            )

            total_deleted += len(deleted_from_group)

            # Ask if user wants to continue with next group
            if group_idx < total_groups:
                continue_review = questionary.confirm(
                    f"\nContinue to next duplicate group? ({group_idx + 1} of {total_groups} remaining)",
                    default=True,
                ).ask()
                if not continue_review:
                    print("\n[cyan]Stopping duplicate review.[/cyan]")
                    break

        # Summary
        if total_deleted > 0:
            print(
                f"\n[green]✅ Deleted {total_deleted} duplicate file(s) in total[/green]"
            )
        else:
            print(f"\n[cyan]No files were deleted[/cyan]")

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
    except Exception as e:
        log_error(
            "DEDUPLICATION",
            f"Unexpected error in deduplication workflow: {e}",
            exception=e,
        )
        print(f"\n[red]❌ An unexpected error occurred: {e}[/red]")


def _discover_all_files(folder_path: Path) -> List[Path]:
    """
    Discover all files in a folder (all file types, not just WAV).

    Args:
        folder_path: Path to folder to search

    Returns:
        List of file paths (excluding hidden files starting with '.')
    """
    files = []

    try:
        # Use os.scandir() which is more efficient than glob() on network mounts
        with os.scandir(folder_path) as entries:
            for entry in entries:
                if entry.is_file() and not entry.name.startswith("."):
                    files.append(Path(entry.path))

        # Sort by name for consistent ordering
        files = sorted(files, key=lambda p: p.name.lower())

    except Exception as e:
        log_error(
            "DEDUPLICATION",
            f"Error discovering files in {folder_path}: {e}",
            exception=e,
        )

    return files


def _precompute_file_metadata(files: List[Path]) -> Dict[Path, Dict]:
    """
    Pre-compute metadata for all files to avoid expensive disk I/O during UI rendering.

    This is critical for performance, especially on USB drives or network mounts.
    Similar to the caching approach used in file_selection_interface.py.

    Args:
        files: List of file paths to pre-compute metadata for

    Returns:
        Dictionary mapping file paths to metadata dicts with 'size_mb' and 'duration' keys
    """
    metadata_cache: Dict[Path, Dict] = {}

    for file_path in files:
        try:
            # Get file size once
            size_bytes = file_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)

            metadata = {"size_mb": size_mb}

            # Get audio duration if it's an audio file
            if _is_audio_file(file_path):
                duration = get_audio_duration(file_path)
                if duration is not None:
                    metadata["duration"] = duration

            metadata_cache[file_path] = metadata
        except Exception as e:
            logger.debug(f"Failed to pre-compute metadata for {file_path}: {e}")
            # Store empty metadata so formatter can still work
            metadata_cache[file_path] = {}

    return metadata_cache


def _create_duplicate_file_formatter(size_bytes: int, metadata_cache: Dict[Path, Dict]):
    """
    Create a custom formatter for duplicate files that shows size and metadata.

    Uses pre-computed metadata from cache to avoid expensive disk I/O.
    This matches the caching pattern used in file_selection_interface.py.

    Args:
        size_bytes: Size of the duplicate files (already known)
        metadata_cache: Dictionary mapping file paths to pre-computed metadata

    Returns:
        Formatter function that takes a Path and returns a formatted string
    """
    size_str = _format_file_size(size_bytes)

    def format_duplicate_file(file_path: Path) -> str:
        """Format duplicate file for display using cached metadata."""
        try:
            # Get pre-computed metadata from cache
            cached_metadata = metadata_cache.get(file_path, {})
            size_mb = cached_metadata.get("size_mb")
            duration = cached_metadata.get("duration")

            # Check if it's an audio file
            if _is_audio_file(file_path):
                # Use cached metadata if available
                if size_mb is not None:
                    if duration is not None:
                        duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
                        return f"🎵 {file_path.name} ({size_mb:.1f} MB, {duration_str}) [DUPLICATE: {size_str}]"
                    else:
                        return f"🎵 {file_path.name} ({size_mb:.1f} MB) [DUPLICATE: {size_str}]"
                else:
                    # Fallback if cache miss (shouldn't happen)
                    return f"🎵 {file_path.name} [DUPLICATE: {size_str}]"
            else:
                # Use cached metadata if available
                if size_mb is not None:
                    return f"📄 {file_path.name} ({size_mb:.1f} MB) [DUPLICATE: {size_str}]"
                else:
                    # Fallback if cache miss (shouldn't happen)
                    return f"📄 {file_path.name} [DUPLICATE: {size_str}]"
        except Exception:
            return f"{file_path.name} [DUPLICATE: {size_str}]"

    return format_duplicate_file


def _review_duplicate_group(
    duplicate_files: List[Path],
    size_bytes: int,
    group_idx: int,
    total_groups: int,
    folder_path: Path,
) -> List[Path]:
    """
    Review a duplicate group using the feature-rich file selection interface.

    Args:
        duplicate_files: List of duplicate file paths
        size_bytes: Size of the duplicate files
        group_idx: Current group index
        total_groups: Total number of groups
        folder_path: Path to the folder being scanned

    Returns:
        List of files that were deleted
    """
    deleted_files: List[Path] = []

    # Pre-compute metadata for all duplicate files upfront
    # This avoids expensive disk I/O during UI rendering
    # Similar to the caching approach used in file_selection_interface.py
    metadata_cache = _precompute_file_metadata(duplicate_files)

    # Create custom formatter for this duplicate group using cached metadata
    formatter = _create_duplicate_file_formatter(size_bytes, metadata_cache)

    # Determine if files are audio files (for playback support)
    are_audio_files = all(_is_audio_file(f) for f in duplicate_files)

    # Use feature-rich file selection interface
    size_str = _format_file_size(size_bytes)
    # Title with warning - keep concise to fit in header
    title = f"🔍 Duplicate Group {group_idx}/{total_groups} - Select files to delete (⚠️  Will be permanently deleted!)"

    selection_config = FileSelectionConfig(
        multi_select=True,
        enable_playback=are_audio_files,
        enable_rename=True,
        enable_select_all=True,  # Allow selecting all duplicates (e.g., when all are unwanted white noise)
        auto_exit_when_one_remains=True,  # Auto-advance to next group when only one file remains
        title=title,
        current_path=folder_path,
        metadata_formatter=formatter,
    )

    # Note: Don't print before select_files_interactive as it interferes with prompt_toolkit
    # The menu header will show the title with the warning
    # Flush stdout to ensure any previous output is displayed before the menu appears
    sys.stdout.flush()
    selected_files = select_files_interactive(duplicate_files, selection_config)

    if not selected_files:
        print(
            "[cyan]No files selected for deletion. Keeping all files in this group.[/cyan]"
        )
        return deleted_files

    # Confirm deletion
    print(
        f"\n[bold yellow]⚠️  Warning: You are about to delete {len(selected_files)} file(s)[/bold yellow]"
    )
    for file_path in selected_files:
        print(f"  • {file_path.name}")

    confirm = questionary.confirm(
        "Are you sure you want to delete these files? This cannot be undone.",
        default=False,
    ).ask()

    if not confirm:
        print("[cyan]Deletion cancelled. Keeping all files.[/cyan]")
        return deleted_files

    # Delete selected files
    print(f"\n[bold]Deleting {len(selected_files)} file(s)...[/bold]")
    for file_path in selected_files:
        try:
            if file_path.exists():
                file_path.unlink()
                deleted_files.append(file_path)
                print(f"  [green]✅ Deleted {file_path.name}[/green]")
            else:
                print(
                    f"  [yellow]⚠️  {file_path.name} no longer exists, skipping[/yellow]"
                )
        except OSError as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            print(f"  [red]❌ Error deleting {file_path.name}: {e}[/red]")

    return deleted_files


def run_deduplicate_non_interactive(
    folder: Path | str,
    files: list[Path] | list[str] | None = None,
    auto_delete: bool = False,
    skip_confirm: bool = False,
) -> dict[str, Any]:
    """
    Run deduplication workflow non-interactively with provided parameters.

    Args:
        folder: Path to folder to scan for duplicates
        files: List of specific files to delete (optional, for non-interactive deletion)
        auto_delete: Automatically delete duplicates without interactive review (default: False, requires files)
        skip_confirm: Skip confirmation prompts (only used with auto_delete) (default: False)

    Returns:
        Dictionary containing deduplication results

    Raises:
        FileNotFoundError: If folder doesn't exist
        ValueError: If invalid parameters provided
    """
    # Convert folder to Path
    if isinstance(folder, str):
        folder = Path(folder)

    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")

    # If files are provided, delete them directly (non-interactive mode)
    if files:
        files_to_delete = [Path(f) if isinstance(f, str) else f for f in files]

        # Validate files exist
        for file_path in files_to_delete:
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")

        # Confirm deletion if not skipped
        if not skip_confirm and auto_delete:
            from rich.prompt import Confirm

            if not Confirm.ask(f"Delete {len(files_to_delete)} file(s)?"):
                return {"status": "cancelled", "deleted": []}

        # Delete files
        print(f"\n[bold]Deleting {len(files_to_delete)} file(s)...[/bold]")
        deleted_files = []
        failed_files = []

        for file_path in files_to_delete:
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_files.append(file_path)
                    print(f"  [green]✅ Deleted {file_path.name}[/green]")
                else:
                    print(
                        f"  [yellow]⚠️  {file_path.name} no longer exists, skipping[/yellow]"
                    )
            except OSError as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                print(f"  [red]❌ Error deleting {file_path.name}: {e}[/red]")
                failed_files.append((file_path, str(e)))

        return {
            "status": "completed",
            "deleted": [str(f) for f in deleted_files],
            "failed": [{"file": str(f), "error": e} for f, e in failed_files],
            "total_deleted": len(deleted_files),
        }

    # Otherwise, scan for duplicates (interactive review still required)
    print("\n[bold cyan]🔍 Find & Remove Duplicates[/bold cyan]")
    print(f"[bold]Scanning folder: {folder}[/bold]")

    # Discover all files
    all_files = _discover_all_files(folder)

    if not all_files:
        print(f"\n[yellow]⚠️ No files found in {folder}[/yellow]")
        return {
            "status": "completed",
            "duplicate_groups": 0,
            "deleted": [],
            "total_deleted": 0,
        }

    print(f"[green]✅ Found {len(all_files)} file(s)[/green]")

    # Find duplicate groups using two-pass detection
    print("\n[bold]Checking for duplicate files...[/bold]")

    # Use content-based detection if available
    from transcriptx.cli.audio_fingerprinting import is_librosa_available
    from transcriptx.cli.main import _check_and_install_librosa

    config = get_config()

    # Lazy initialization: check and install librosa if needed
    if not is_librosa_available():
        _check_and_install_librosa(allow_install=False)

    if is_librosa_available():
        duplicate_groups = find_duplicate_files_by_size_and_content(
            all_files,
            threshold=config.output.audio_deduplication_threshold,
            show_progress=True,
        )
    else:
        duplicate_groups = find_duplicate_files_by_size(all_files)

    if not duplicate_groups:
        print("\n[green]✅ No duplicate files found![/green]")
        return {
            "status": "completed",
            "duplicate_groups": 0,
            "deleted": [],
            "total_deleted": 0,
        }

    # Sort groups by size (largest first)
    sorted_groups = sorted(duplicate_groups.items(), key=lambda x: x[0], reverse=True)
    total_groups = len(sorted_groups)

    # Determine detection method for display
    detection_method = (
        "size and audio content" if is_librosa_available() else "file size"
    )
    print(
        f"\n[bold yellow]🔍 Found {total_groups} duplicate group(s) (matched by {detection_method})[/bold yellow]"
    )

    # For non-interactive mode without files list, we can't auto-delete
    # Return the duplicate groups for the user to review
    if not auto_delete:
        print(
            "\n[yellow]⚠️ Interactive review required. Use --files to specify files to delete non-interactively.[/yellow]"
        )
        return {
            "status": "requires_interaction",
            "duplicate_groups": total_groups,
            "groups": [
                {
                    "size_bytes": size_bytes,
                    "size_mb": size_bytes / (1024 * 1024),
                    "file_count": len(duplicate_files),
                    "files": [str(f) for f in duplicate_files],
                }
                for size_bytes, duplicate_files in sorted_groups
            ],
        }

    # If auto_delete is True but no files provided, we can't proceed
    raise ValueError(
        "auto_delete requires --files parameter to specify which files to delete"
    )
