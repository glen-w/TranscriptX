"""Merge audio files workflow (interactive and non-interactive)."""

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from rich import print

from transcriptx.cli.file_selection_utils import AUDIO_EXTENSIONS
from transcriptx.core.utils.file_rename import extract_date_prefix
from transcriptx.core.utils.logger import log_error
from transcriptx.core.utils.paths import RECORDINGS_DIR

from . import (
    backup_audio_files_to_storage,
    check_ffmpeg_available,
    merge_audio_files,
    questionary,
    reorder_files_interactive,
    select_audio_files_interactive,
)

from . import (
    collect_audio_file_infos,
    create_audio_progress,
    print_audio_file_list,
    run_workflow_safely,
)


def _run_merge_workflow() -> None:
    """Run the merge audio files workflow."""

    def _body() -> None:
        print("\n[bold cyan]🔗 Merge Audio Files[/bold cyan]")
        print("[dim]Select audio files to merge[/dim]")

        audio_files = select_audio_files_interactive(
            start_path=Path("/Volumes/"), extensions=AUDIO_EXTENSIONS
        )
        if not audio_files:
            print("\n[yellow]⚠️ No audio files selected. Returning to menu.[/yellow]")
            return

        if len(audio_files) < 2:
            print("\n[red]❌ Please select at least 2 audio files to merge.[/red]")
            return

        print("\n[bold cyan]📋 File Order[/bold cyan]")
        print("[dim]You can reorder the files to control the merge sequence.[/dim]")
        audio_files = reorder_files_interactive(audio_files)
        if not audio_files:
            print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
            return

        infos = collect_audio_file_infos(audio_files)
        print_audio_file_list(infos, show_total=True, show_total_duration=True)

        date_prefix = extract_date_prefix(audio_files[0]) if audio_files else ""
        default_filename = (
            f"{date_prefix}merged.mp3"
            if date_prefix
            else f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        )
        output_filename = questionary.text(
            "Enter output filename (or press Enter for default):",
            default=default_filename,
        ).ask()

        if not output_filename:
            output_filename = default_filename

        if not output_filename.endswith(".mp3"):
            output_filename += ".mp3"

        output_dir = Path(RECORDINGS_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_filename

        if output_path.exists():
            if not questionary.confirm(
                f"File {output_filename} already exists. Overwrite?"
            ).ask():
                print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
                return

        if not questionary.confirm(
            f"\nMerge {len(audio_files)} files into {output_filename}?"
        ).ask():
            print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
            return

        print("\n[bold]Backing up audio files to storage...[/bold]")
        try:
            base_name = Path(output_filename).stem
            backup_paths = backup_audio_files_to_storage(
                audio_files, base_name=base_name
            )
            if backup_paths:
                print(
                    f"[green]✅ Backed up {len(backup_paths)} file(s) to storage[/green]"
                )
                audio_files = backup_paths
            else:
                print(
                    "[yellow]⚠️ Warning: No files were backed up. Continuing with merge...[/yellow]"
                )
        except Exception as e:
            log_error("AUDIO_BACKUP", f"Error backing up audio files: {e}", exception=e)
            print(
                f"[yellow]⚠️ Warning: Backup failed: {e}. Continuing with merge...[/yellow]"
            )

        print("\n[bold]Merging files...[/bold]")
        print(f"[dim]Output file: {output_path}[/dim]")

        start_time = time.time()
        total_duration = sum(i.duration_seconds for i in infos)

        with create_audio_progress(show_pct=True) as progress:
            task = progress.add_task(
                "[cyan]Merging audio files...", total=len(audio_files)
            )

            def progress_callback(current: int, total: int, message: str):
                progress.update(task, advance=1, description=f"[cyan]{message}[/cyan]")

            try:
                output_path = merge_audio_files(
                    audio_files, output_path, progress_callback=progress_callback
                )

                progress.update(
                    task,
                    completed=len(audio_files),
                    description="[green]✅ Merge completed![/green]",
                )

            except Exception as e:
                progress.update(task, description=f"[red]❌ Merge failed: {e}[/red]")
                raise

        elapsed_time = time.time() - start_time

        print("\n[bold green]✅ Merge Complete![/bold green]")
        print(
            f"[green]Successfully merged {len(audio_files)} files into: {output_path.name}[/green]"
        )
        print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")
        print(f"[dim]Output file: {output_path}[/dim]")

        if total_duration > 0:
            total_duration_str = (
                f"{int(total_duration // 60)}:{int(total_duration % 60):02d}"
            )
            print(f"[dim]Total duration: {total_duration_str}[/dim]")

    if (
        run_workflow_safely(
            "AUDIO_MERGE",
            _body,
            interactive=True,
            cancelled_message="\n[cyan]Merge cancelled. Returning to menu.[/cyan]",
        )
        is not None
    ):
        return


def run_wav_merge_non_interactive(
    files: list[Path] | list[str],
    output_file: str | None = None,
    output_dir: Path | str | None = None,
    backup_wavs: bool = True,
    overwrite: bool = False,
    skip_confirm: bool = False,
) -> dict[str, Any]:
    """
    Merge multiple WAV files into one MP3 non-interactively.

    Args:
        files: List of WAV file paths in merge order (minimum 2)
        output_file: Output MP3 filename (default: auto-generated with date prefix)
        output_dir: Output directory (default: RECORDINGS_DIR)
        backup_wavs: Backup WAV files to storage before merging (default: True)
        overwrite: Overwrite output file if it exists (default: False)
        skip_confirm: Skip confirmation prompts (default: False)

    Returns:
        Dictionary containing merge results
    """
    ffmpeg_available, error_msg = check_ffmpeg_available()
    if not ffmpeg_available:
        raise RuntimeError(f"ffmpeg not available: {error_msg}")

    audio_files = [Path(f) if isinstance(f, str) else f for f in files]

    if len(audio_files) < 2:
        raise ValueError("At least 2 audio files are required for merging")

    for af in audio_files:
        if not af.exists():
            raise FileNotFoundError(f"Audio file not found: {af}")
        if af.suffix.lower() not in AUDIO_EXTENSIONS:
            raise ValueError(
                f"File is not a supported audio format: {af} (allowed: {AUDIO_EXTENSIONS})"
            )

    if output_dir is None:
        output_dir = Path(RECORDINGS_DIR)
    elif isinstance(output_dir, str):
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not output_file:
        date_prefix = extract_date_prefix(audio_files[0]) if audio_files else ""
        output_file = (
            f"{date_prefix}merged.mp3"
            if date_prefix
            else f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        )

    if not output_file.endswith(".mp3"):
        output_file += ".mp3"

    output_path = output_dir / output_file

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output file already exists: {output_path}. Use --overwrite to overwrite."
        )

    infos = collect_audio_file_infos(audio_files)
    print_audio_file_list(infos, show_total=True, show_total_duration=True)
    print(f"[dim]Output file: {output_path}[/dim]")

    if not skip_confirm:
        from rich.prompt import Confirm

        if not Confirm.ask(f"Merge {len(audio_files)} files into {output_file}?"):
            return {"status": "cancelled"}

    if backup_wavs:
        print("\n[bold]Backing up audio files to storage...[/bold]")
        try:
            base_name = Path(output_file).stem
            backup_paths = backup_audio_files_to_storage(
                audio_files, base_name=base_name
            )
            if backup_paths:
                print(
                    f"[green]✅ Backed up {len(backup_paths)} file(s) to storage[/green]"
                )
                audio_files = backup_paths
            else:
                print(
                    "[yellow]⚠️ Warning: No files were backed up. Continuing with merge...[/yellow]"
                )
        except Exception as e:
            log_error("AUDIO_BACKUP", f"Error backing up audio files: {e}", exception=e)
            print(
                f"[yellow]⚠️ Warning: Backup failed: {e}. Continuing with merge...[/yellow]"
            )

    print("\n[bold]Merging files...[/bold]")
    start_time = time.time()

    with create_audio_progress(show_pct=True) as progress:
        task = progress.add_task("[cyan]Merging audio files...", total=len(audio_files))

        def progress_callback(current: int, total: int, message: str):
            progress.update(task, advance=1, description=f"[cyan]{message}[/cyan]")

        try:
            output_path = merge_audio_files(
                audio_files, output_path, progress_callback=progress_callback
            )
            progress.update(
                task,
                completed=len(audio_files),
                description="[green]✅ Merge completed![/green]",
            )
        except Exception as e:
            progress.update(task, description=f"[red]❌ Merge failed: {e}[/red]")
            raise

    elapsed_time = time.time() - start_time

    print("\n[bold green]✅ Merge Complete![/bold green]")
    print(
        f"[green]Successfully merged {len(audio_files)} files into: {output_path.name}[/green]"
    )
    print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")

    return {
        "status": "completed",
        "output_file": str(output_path),
        "files_merged": len(audio_files),
        "backed_up": backup_wavs,
    }
