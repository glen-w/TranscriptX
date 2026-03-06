"""
Shared UI helpers for WAV processing workflows.

Provides progress bars, file list formatting, workflow error handling,
and post-conversion backup/cleanup so workflow code stays DRY.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Literal, TypeVar

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)

from transcriptx.cli.audio import (
    backup_audio_files_to_storage,
    backup_wav_after_processing,
    check_wav_backup_exists,
    get_audio_duration,
)
from transcriptx.core.utils.logger import log_error

_T = TypeVar("_T")


# --- Progress factory -------------------------------------------------------


def create_audio_progress(
    show_pct: bool = True,
    *,
    progress_cls: type[Progress] = Progress,
    console: Console | None = None,
) -> Progress:
    """Build a Rich Progress with standard columns for audio workflows.

    Callers in wav_processing_workflow use wrappers that call this, so
    tests can patch Progress at the workflow module.
    """
    if console is None:
        console = Console()
    columns = [
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
    ]
    if show_pct:
        columns.append(TextColumn("[progress.percentage]{task.percentage:>3.0f}%"))
    columns.append(TimeRemainingColumn())
    return progress_cls(*columns, console=console)


# --- File list: data + print -------------------------------------------------


class AudioFileInfo:
    """Per-file metadata for display and reuse."""

    __slots__ = ("path", "size_mb", "duration_seconds", "duration_str")

    def __init__(
        self,
        path: Path,
        size_mb: float,
        duration_seconds: float | None,
        duration_str: str | None,
    ) -> None:
        self.path = path
        self.size_mb = size_mb
        self.duration_seconds = duration_seconds or 0.0
        self.duration_str = duration_str or ""


def collect_audio_file_infos(
    files: list[Path],
    get_duration: Callable[[Path], float | None] | None = None,
) -> list[AudioFileInfo]:
    """Compute per-file metadata (size, duration) for audio files."""
    if get_duration is None:
        get_duration = get_audio_duration
    infos: list[AudioFileInfo] = []
    for f in files:
        size_mb = f.stat().st_size / (1024 * 1024)
        duration_sec = get_duration(f)
        if duration_sec is not None:
            duration_str = f"{int(duration_sec // 60)}:{int(duration_sec % 60):02d}"
        else:
            duration_str = ""
        infos.append(
            AudioFileInfo(
                path=f,
                size_mb=size_mb,
                duration_seconds=duration_sec if duration_sec is not None else 0.0,
                duration_str=duration_str,
            )
        )
    return infos


def print_audio_file_list(
    infos: list[AudioFileInfo],
    *,
    show_total: bool = False,
    show_total_duration: bool = False,
) -> None:
    """Print 'Selected N file(s)' header and per-file lines; optionally totals."""
    from rich import print as rprint

    if not infos:
        return
    rprint(f"\n[bold]Selected {len(infos)} file(s):[/bold]")
    for idx, info in enumerate(infos, 1):
        if info.duration_str:
            rprint(
                f"  {idx}. {info.path.name} ({info.size_mb:.1f} MB, {info.duration_str})"
            )
        else:
            rprint(f"  {idx}. {info.path.name} ({info.size_mb:.1f} MB)")
    if show_total or show_total_duration:
        total_mb = sum(i.size_mb for i in infos)
        total_sec = sum(i.duration_seconds for i in infos)
        rprint(f"\n[dim]Total size: {total_mb:.1f} MB[/dim]")
        if show_total_duration and total_sec > 0:
            total_str = f"{int(total_sec // 60)}:{int(total_sec % 60):02d}"
            rprint(f"[dim]Estimated total duration: {total_str}[/dim]")


# --- Workflow error wrapper --------------------------------------------------


def run_workflow_safely(
    label: str,
    fn: Callable[[], _T],
    *,
    interactive: bool = True,
    cancelled_message: str = "\n[cyan]Cancelled. Returning to menu.[/cyan]",
) -> _T | Literal["cancelled", "error"]:
    """Run a workflow function with consistent KeyboardInterrupt and Exception handling.

    - KeyboardInterrupt: print cancelled_message, return "cancelled".
    - Exception: log_error(label, ...); if interactive, print generic error and return "error";
      otherwise re-raise.
    """
    from rich import print as rprint

    try:
        return fn()
    except KeyboardInterrupt:
        rprint(cancelled_message)
        return "cancelled"
    except Exception as e:
        log_error(label, f"Error: {e}", exception=e)
        if interactive:
            rprint(f"\n[red]❌ An unexpected error occurred: {e}[/red]")
            return "error"
        raise


# --- Post-convert backup and cleanup ----------------------------------------


def post_convert_backup_and_cleanup(
    pairs: list[tuple[Path, Path]],
    *,
    delete_originals_if_already_backed_up: bool,
    kind: Literal["wav", "audio"] = "wav",
) -> tuple[int, int, int]:
    """Move originals to storage and optionally delete. Prints progress; no prompts.

    Returns (moved_count, failed_count, skipped_count). skipped_count is the number
    of originals that were already backed up and were only deleted (counted in moved_count).
    """
    from rich import print as rprint

    moved_count = 0
    failed_count = 0
    skipped_count = 0

    for orig_file, mp3_path in pairs:
        if not orig_file.exists():
            rprint(f"  ⚠️  {orig_file.name} no longer exists, skipping")
            continue
        if kind == "wav" and orig_file.suffix.lower() == ".wav":
            existing_backup = check_wav_backup_exists(orig_file, mp3_path=mp3_path)
            if existing_backup:
                if delete_originals_if_already_backed_up:
                    try:
                        orig_file.unlink()
                        moved_count += 1
                        skipped_count += 1
                        rprint(
                            f"  ✅ Deleted {orig_file.name} (already backed up as {existing_backup.name})"
                        )
                    except Exception as e:
                        failed_count += 1
                        rprint(f"  ❌ Failed to delete {orig_file.name}: {e}")
            else:
                backup_path = backup_wav_after_processing(
                    orig_file,
                    mp3_path=mp3_path,
                    target_name=None,
                    delete_original=True,
                )
                if backup_path:
                    moved_count += 1
                    rprint(f"  ✅ Moved {orig_file.name} → {backup_path.name}")
                else:
                    failed_count += 1
                    rprint(f"  ❌ Failed to move {orig_file.name}")
        else:
            backup_paths = backup_audio_files_to_storage(
                [orig_file], base_name=mp3_path.stem, delete_original=True
            )
            if backup_paths:
                moved_count += 1
                rprint(f"  ✅ Moved {orig_file.name} → {backup_paths[0].name}")
            else:
                failed_count += 1
                rprint(f"  ❌ Failed to move {orig_file.name}")

    return (moved_count, failed_count, skipped_count)
