"""
File discovery and filtering utilities for batch workflows.

This module provides functions for discovering WAV files, filtering by various
criteria, and interactive file selection.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import os

import questionary
from rich import print

from transcriptx.cli.processing_state import is_file_processed, load_processing_state
from transcriptx.cli.file_selection_interface import (
    FileSelectionConfig,
    select_files_interactive as select_files_with_interface,
    format_audio_file,
)
from transcriptx.cli.file_selection_utils import validate_wav_file
from transcriptx.cli.file_selection_interface import _is_audio_file
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.config import get_config
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.console import Console

logger = get_logger()
console = Console()


def discover_audio_files(
    folder_path: Path,
    extensions: tuple[str, ...] = (".wav", ".mp3", ".ogg", ".m4a", ".flac", ".aac"),
) -> List[Path]:
    """
    Discover all audio files in a folder with the given extensions.

    Args:
        folder_path: Path to folder to search
        extensions: Tuple of allowed suffixes (e.g. (".wav", ".mp3", ".ogg"))

    Returns:
        List of audio file paths (excluding hidden files starting with '.')
    """
    ext_set = {e.lower() if e.startswith(".") else f".{e}".lower() for e in extensions}

    files = []
    try:
        with os.scandir(folder_path) as entries:
            for entry in entries:
                if entry.is_file() and not entry.name.startswith("."):
                    name_lower = entry.name.lower()
                    if any(name_lower.endswith(ext) for ext in ext_set):
                        files.append(Path(entry.path))

        files = sorted(files, key=lambda p: p.name.lower())

    except Exception as e:
        log_error(
            "FILE_DISCOVERY",
            f"Error discovering audio files in {folder_path}: {e}",
            exception=e,
        )

    return files


def discover_wav_files(folder_path: Path) -> List[Path]:
    """
    Discover all WAV files in a folder. Thin wrapper around discover_audio_files.
    """
    return discover_audio_files(folder_path, (".wav",))


def filter_new_files(wav_files: List[Path]) -> List[Path]:
    """
    Filter out files that have already been processed.

    Args:
        wav_files: List of WAV file paths

    Returns:
        List of unprocessed WAV file paths
    """
    state = load_processing_state()
    new_files = []

    for wav_file in wav_files:
        if not is_file_processed(wav_file, state):
            new_files.append(wav_file)

    return new_files


def filter_files_by_size(
    wav_files: List[Path],
    min_size_mb: Optional[float] = None,
    max_size_mb: Optional[float] = None,
) -> List[Path]:
    """
    Filter WAV files by size.

    Args:
        wav_files: List of WAV file paths
        min_size_mb: Minimum file size in MB (inclusive)
        max_size_mb: Maximum file size in MB (exclusive)

    Returns:
        List of WAV file paths matching the size criteria
    """
    filtered = []

    for wav_file in wav_files:
        try:
            size_bytes = wav_file.stat().st_size
            size_mb = size_bytes / (1024 * 1024)

            # Check size criteria
            if min_size_mb is not None and size_mb < min_size_mb:
                continue
            if max_size_mb is not None and size_mb >= max_size_mb:
                continue

            filtered.append(wav_file)
        except (OSError, FileNotFoundError) as e:
            logger.warning(f"Could not get size for {wav_file}: {e}")
            continue

    return filtered


def find_duplicate_files_by_size(files: List[Path]) -> Dict[int, List[Path]]:
    """
    Group files by their exact file size and return only groups with duplicates.

    Args:
        files: List of file paths to check

    Returns:
        Dictionary mapping file sizes (bytes) to lists of files with that size.
        Only includes sizes that have 2+ files (actual duplicates).
    """
    size_groups: Dict[int, List[Path]] = {}

    for file in files:
        try:
            size = file.stat().st_size
            if size not in size_groups:
                size_groups[size] = []
            size_groups[size].append(file)
        except OSError as e:
            logger.warning(f"Could not get size for {file}: {e}")
            continue

    # Return only groups with duplicates (2+ files) that share identical content.
    duplicate_groups: Dict[int, List[Path]] = {}
    for size, group in size_groups.items():
        if len(group) < 2:
            continue
        content_groups: Dict[bytes, List[Path]] = {}
        for file in group:
            try:
                content = file.read_bytes()
            except OSError as e:
                logger.warning(f"Could not read {file}: {e}")
                continue
            content_groups.setdefault(content, []).append(file)
        for matches in content_groups.values():
            if len(matches) > 1:
                duplicate_groups[size] = matches
                break
    return duplicate_groups


def find_duplicate_files_by_size_and_content(
    files: List[Path], threshold: Optional[float] = None, show_progress: bool = True
) -> Dict[int, List[Path]]:
    """
    Find duplicate files using two-pass detection: size first, then audio content.

    This function performs a two-stage duplicate detection:
    1. First pass (fast): Group files by identical file size
    2. Second pass (content-based): For size-matched groups, compare audio content
       using fingerprinting to verify actual duplicates

    This solves the problem where dictation devices create multiple files with
    identical 1-hour cutoffs (same size/duration) but different audio content.

    Args:
        files: List of file paths to check
        threshold: Similarity threshold for audio comparison (0.0 to 1.0).
                   If None, uses config value (default: 0.90)
        show_progress: Whether to show progress during audio comparison (default: True)

    Returns:
        Dictionary mapping file sizes (bytes) to lists of files that are duplicates.
        Only includes groups where files match in size AND audio content.

    Note:
        - Non-audio files are only compared by size (no content comparison)
        - If librosa is not available, falls back to size-only detection with warning
        - Audio comparison can be slow for large groups; progress is shown if enabled
    """
    from transcriptx.cli.audio_fingerprinting import (
        batch_compare_audio_group,
        is_librosa_available,
        clear_fingerprint_cache,
    )

    # Get threshold from config if not provided
    if threshold is None:
        config = get_config()
        threshold = config.output.audio_deduplication_threshold

    # First pass: Group by size (fast)
    size_groups = find_duplicate_files_by_size(files)

    if not size_groups:
        return {}

    # Check if librosa is available for content-based comparison
    librosa_available = is_librosa_available()

    if not librosa_available:
        logger.warning(
            "librosa is not available. Falling back to size-only duplicate detection. "
            "Install librosa for content-based duplicate detection: pip install librosa>=0.10.0"
        )
        return size_groups

    # Second pass: Content-based comparison for size-matched groups
    verified_duplicate_groups: Dict[int, List[Path]] = {}
    total_groups = len(size_groups)
    groups_processed = 0

    # Clear fingerprint cache at start
    clear_fingerprint_cache()

    # Progress tracking
    progress = None
    if show_progress:
        progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        )
        progress.start()
        task = progress.add_task(
            f"Comparing audio content for {total_groups} size-matched group(s)...",
            total=total_groups,
        )

    try:
        for size_bytes, size_matched_files in size_groups.items():
            groups_processed += 1

            # Separate audio and non-audio files
            audio_files = [f for f in size_matched_files if _is_audio_file(f)]
            non_audio_files = [f for f in size_matched_files if not _is_audio_file(f)]

            # For non-audio files, we can only compare by size
            # If there are 2+ non-audio files with same size, consider them duplicates
            if len(non_audio_files) > 1:
                # Merge with audio duplicates if any, or create new group
                if size_bytes not in verified_duplicate_groups:
                    verified_duplicate_groups[size_bytes] = []
                verified_duplicate_groups[size_bytes].extend(non_audio_files)

            # For audio files, perform content-based comparison
            if len(audio_files) > 1:
                try:
                    # Compare audio content
                    duplicate_groups = batch_compare_audio_group(
                        audio_files, threshold=threshold, use_cache=True
                    )

                    # Add verified duplicate groups
                    for (
                        representative_file,
                        duplicate_group,
                    ) in duplicate_groups.items():
                        if size_bytes not in verified_duplicate_groups:
                            verified_duplicate_groups[size_bytes] = []
                        verified_duplicate_groups[size_bytes].extend(duplicate_group)

                except Exception as e:
                    log_error(
                        "DUPLICATE_DETECTION",
                        f"Error comparing audio content for group of size {size_bytes}: {e}",
                        exception=e,
                    )
                    # Fallback: if content comparison fails, use size-only for this group
                    if size_bytes not in verified_duplicate_groups:
                        verified_duplicate_groups[size_bytes] = []
                    verified_duplicate_groups[size_bytes].extend(audio_files)

            # Update progress
            if progress:
                progress.update(task, completed=groups_processed)

    finally:
        if progress:
            progress.stop()

    # Only return groups with 2+ files (actual duplicates)
    return {
        size: group
        for size, group in verified_duplicate_groups.items()
        if len(group) > 1
    }


def _format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: File size in bytes

    Returns:
        Formatted string (e.g., "1.5 MB", "512 KB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def _format_file_details(file_path: Path) -> str:
    """
    Format file details for display.

    Args:
        file_path: Path to file

    Returns:
        Formatted string with file details
    """
    try:
        stat = file_path.stat()
        size_str = _format_file_size(stat.st_size)
        mod_time = datetime.fromtimestamp(stat.st_mtime)
        mod_time_str = mod_time.strftime("%Y-%m-%d %H:%M:%S")
        return f"{file_path.name} | {size_str} | Modified: {mod_time_str} | {file_path.parent}"
    except OSError as e:
        logger.warning(f"Could not get details for {file_path}: {e}")
        return f"{file_path.name} | {file_path.parent}"


def review_and_delete_duplicates(files: List[Path]) -> List[Path]:
    """
    Review duplicate files and allow user to delete selected ones.

    Files are grouped by identical file size. For each group, the user is
    shown the file details and can select which file(s) to delete, or keep all.

    Args:
        files: List of file paths to check for duplicates

    Returns:
        List of files that were deleted
    """
    deleted_files: List[Path] = []

    # Find duplicate groups
    duplicate_groups = find_duplicate_files_by_size(files)

    if not duplicate_groups:
        return deleted_files

    # Sort groups by size (largest first) for review
    sorted_groups = sorted(duplicate_groups.items(), key=lambda x: x[0], reverse=True)
    total_groups = len(sorted_groups)

    print(
        f"\n[bold yellow]🔍 Found {total_groups} duplicate group(s) (files with identical sizes)[/bold yellow]"
    )

    for group_idx, (size_bytes, duplicate_files) in enumerate(sorted_groups, 1):
        size_str = _format_file_size(size_bytes)
        num_files = len(duplicate_files)

        print(f"\n[bold cyan]Duplicate Group {group_idx} of {total_groups}[/bold cyan]")
        print(f"[dim]Size: {size_str} | {num_files} file(s) with identical size[/dim]")
        print("\n[bold]Files:[/bold]")

        # Display file details
        for idx, file_path in enumerate(duplicate_files, 1):
            details = _format_file_details(file_path)
            print(f"  {idx}. {details}")

        # Create choices for user selection
        choices = []
        for idx, file_path in enumerate(duplicate_files, 1):
            choices.append(f"{idx}. Delete {file_path.name}")
        choices.append("Keep all files")

        # Prompt user to select which files to delete
        selection = questionary.select(
            "\nSelect file(s) to delete from this group (or keep all):",
            choices=choices,
            default=choices[-1],  # Default to "Keep all"
        ).ask()

        if not selection or selection == "Keep all files":
            print("[cyan]Keeping all files in this group[/cyan]")
            continue

        # Parse selection - extract file index
        try:
            # Selection format: "1. Delete filename.wav"
            selected_idx = int(selection.split(".")[0]) - 1
            if 0 <= selected_idx < len(duplicate_files):
                file_to_delete = duplicate_files[selected_idx]

                # Confirm deletion
                confirm = questionary.confirm(
                    f"Delete {file_to_delete.name}?", default=False
                ).ask()

                if confirm:
                    try:
                        file_to_delete.unlink()
                        deleted_files.append(file_to_delete)
                        print(f"[green]✓ Deleted {file_to_delete.name}[/green]")
                    except OSError as e:
                        logger.error(f"Failed to delete {file_to_delete}: {e}")
                        print(
                            f"[red]❌ Error deleting {file_to_delete.name}: {e}[/red]"
                        )
                else:
                    print(f"[cyan]Cancelled deletion of {file_to_delete.name}[/cyan]")
        except (ValueError, IndexError) as e:
            logger.warning(f"Could not parse selection: {selection}, error: {e}")
            print("[yellow]⚠️ Invalid selection, skipping this group[/yellow]")

    if deleted_files:
        print(f"\n[green]✅ Deleted {len(deleted_files)} duplicate file(s)[/green]")
    else:
        print("\n[cyan]No files were deleted[/cyan]")

    return deleted_files


def select_files_interactive(wav_files: List[Path]) -> List[Path]:
    """
    Let user select which files to process.

    Args:
        wav_files: List of WAV file paths

    Returns:
        List of selected file paths
    """
    if not wav_files:
        return []

    # Use the new generic selection interface
    config = get_config()
    selection_config = FileSelectionConfig(
        multi_select=True,
        enable_playback=True,
        enable_rename=True,
        enable_select_all=True,
        title="🎵 WAV File Selection",
        metadata_formatter=format_audio_file,
        validator=validate_wav_file,
        skip_seconds_short=config.input.playback_skip_seconds_short,
        skip_seconds_long=config.input.playback_skip_seconds_long,
    )

    selected = select_files_with_interface(wav_files, selection_config)
    return selected if selected else []
