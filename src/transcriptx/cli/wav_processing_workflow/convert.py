"""Convert audio files to MP3 workflow (interactive and non-interactive)."""

import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from rich import print

from transcriptx.cli.audio import backup_wav_after_processing, check_wav_backup_exists
from transcriptx.cli.file_selection_utils import AUDIO_EXTENSIONS
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import RECORDINGS_DIR

from . import (
    check_ffmpeg_available,
    convert_audio_to_mp3,
    get_wav_folder_start_path,
    questionary,
    rename_mp3_after_conversion,
    select_audio_files_interactive,
)

from . import (
    collect_audio_file_infos,
    create_audio_progress,
    post_convert_backup_and_cleanup,
    print_audio_file_list,
    run_workflow_safely,
)

logger = get_logger()


def _run_convert_workflow() -> None:
    """Run the convert to MP3 workflow."""

    def _body() -> None:
        from transcriptx.core.utils.config import get_config

        print("\n[bold cyan]🔄 Convert to MP3[/bold cyan]")
        print("[dim]Select audio files to convert[/dim]")

        config = get_config()
        start_path = get_wav_folder_start_path(config)
        audio_files = select_audio_files_interactive(
            start_path=start_path, extensions=AUDIO_EXTENSIONS
        )
        if not audio_files:
            print("\n[yellow]⚠️ No audio files selected. Returning to menu.[/yellow]")
            return

        if len(audio_files) == 0:
            print("\n[red]❌ No valid audio files selected.[/red]")
            return

        infos = collect_audio_file_infos(audio_files)
        print_audio_file_list(infos, show_total=True)

        if not questionary.confirm(
            f"\nConvert {len(audio_files)} file(s) to MP3?"
        ).ask():
            print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
            return

        output_dir = Path(RECORDINGS_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        print("\n[bold]Converting files...[/bold]")
        print(f"[dim]Output directory: {output_dir}[/dim]")

        start_time = time.time()
        successful_conversions = []
        failed_conversions = []

        with create_audio_progress(show_pct=True) as progress:
            task = progress.add_task(
                "[cyan]Converting audio files...", total=len(audio_files)
            )

            for idx, af in enumerate(audio_files, 1):
                try:
                    file_size_mb = af.stat().st_size / (1024 * 1024)
                    progress.update(
                        task,
                        description=f"[cyan]Converting {af.name} ({file_size_mb:.1f} MB)...[/cyan]",
                    )

                    output_path = convert_audio_to_mp3(af, output_dir)

                    successful_conversions.append((af, output_path))
                    progress.update(
                        task,
                        advance=1,
                        description=f"[green]✅ Converted {af.name}[/green]",
                    )

                except Exception as e:
                    failed_conversions.append((af, str(e)))
                    log_error(
                        "AUDIO_CONVERSION",
                        f"Failed to convert {af.name}: {e}",
                        exception=e,
                    )
                    progress.update(
                        task,
                        advance=1,
                        description=f"[red]❌ Failed {af.name}[/red]",
                    )

        elapsed_time = time.time() - start_time

        print("\n[bold green]✅ Conversion Complete![/bold green]")
        print(
            f"[green]Successfully converted: {len(successful_conversions)}/{len(audio_files)} files[/green]"
        )
        print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")
        print(f"[dim]Output directory: {output_dir}[/dim]")

        if successful_conversions:
            print("\n[bold]Converted files:[/bold]")
            for orig_file, output_path in successful_conversions:
                print(f"  ✅ {orig_file.name} → {output_path.name}")

        if failed_conversions:
            print("\n[yellow]⚠️ Failed conversions:[/yellow]")
            for orig_file, error in failed_conversions:
                print(f"  ❌ {orig_file.name}: {error}")

        if successful_conversions:
            renamed_paths = []
            for orig_file, output_path in successful_conversions:
                renamed_path = rename_mp3_after_conversion(output_path)
                renamed_paths.append((orig_file, renamed_path))

            successful_conversions = renamed_paths

            backed_up_count = 0
            already_backed_up_count = 0
            for orig_file, mp3_path in successful_conversions:
                if orig_file.exists() and orig_file.suffix.lower() == ".wav":
                    existing_backup = check_wav_backup_exists(
                        orig_file, mp3_path=mp3_path
                    )
                    if not existing_backup:
                        backup_path = backup_wav_after_processing(
                            orig_file,
                            mp3_path=mp3_path,
                            target_name=None,
                            delete_original=False,
                        )
                        if backup_path:
                            backed_up_count += 1
                            logger.info(
                                f"Automatically backed up {orig_file.name} to {backup_path.name}"
                            )
                    else:
                        already_backed_up_count += 1
                        logger.debug(
                            f"{orig_file.name} already backed up as {existing_backup.name}"
                        )

            if backed_up_count > 0 or already_backed_up_count > 0:
                if backed_up_count > 0:
                    print(
                        f"[dim]✅ Automatically backed up {backed_up_count} audio file(s) to storage[/dim]"
                    )
                if already_backed_up_count > 0:
                    print(
                        f"[dim]ℹ️  {already_backed_up_count} audio file(s) were already backed up[/dim]"
                    )

        if successful_conversions:
            orig_mp3_pairs = [
                (orig_file, mp3_path) for orig_file, mp3_path in successful_conversions
            ]
            if orig_mp3_pairs:
                print("\n[bold cyan]📁 Audio File Management[/bold cyan]")
                print(
                    f"[dim]You have {len(orig_mp3_pairs)} original audio file(s) that can be moved to storage.[/dim]"
                )

                backed_up_files = []
                not_backed_up_files = []
                for orig_file, mp3_path in orig_mp3_pairs:
                    if orig_file.exists():
                        if orig_file.suffix.lower() == ".wav":
                            existing_backup = check_wav_backup_exists(
                                orig_file, mp3_path=mp3_path
                            )
                            if existing_backup:
                                backed_up_files.append(
                                    (orig_file, mp3_path, existing_backup)
                                )
                            else:
                                not_backed_up_files.append((orig_file, mp3_path))
                        else:
                            not_backed_up_files.append((orig_file, mp3_path))

                if backed_up_files:
                    print(
                        f"\n[green]✅ {len(backed_up_files)} file(s) already backed up:[/green]"
                    )
                    for orig_file, mp3_path, backup_path in backed_up_files:
                        print(f"  • {orig_file.name} → {backup_path.name}")

                if not_backed_up_files:
                    print(
                        f"\n[yellow]⚠️  {len(not_backed_up_files)} file(s) not yet backed up:[/yellow]"
                    )
                    for orig_file, mp3_path in not_backed_up_files:
                        print(f"  • {orig_file.name}")

                should_move = questionary.confirm(
                    f"Move {len(orig_mp3_pairs)} audio file(s) to storage and delete originals?",
                    default=False,
                ).ask()

                if should_move:
                    print("\n[bold]Moving audio files to storage...[/bold]")
                    moved_count, failed_count, skipped_count = (
                        post_convert_backup_and_cleanup(
                            orig_mp3_pairs,
                            delete_originals_if_already_backed_up=True,
                            kind="wav",
                        )
                    )
                    if moved_count > 0:
                        if skipped_count > 0:
                            print(
                                f"\n[green]✅ Successfully processed {moved_count} audio file(s) ({skipped_count} already backed up, {moved_count - skipped_count} newly backed up)[/green]"
                            )
                        else:
                            print(
                                f"\n[green]✅ Successfully moved {moved_count} audio file(s) to storage[/green]"
                            )
                    if failed_count > 0:
                        print(
                            f"\n[yellow]⚠️  Failed to process {failed_count} audio file(s)[/yellow]"
                        )
                else:
                    print("\n[cyan]Keeping original audio files[/cyan]")

    if (
        run_workflow_safely(
            "WAV_CONVERSION",
            _body,
            interactive=True,
            cancelled_message="\n[cyan]Conversion cancelled. Returning to menu.[/cyan]",
        )
        is not None
    ):
        return


def run_wav_convert_non_interactive(
    files: list[Path] | list[str],
    output_dir: Path | str | None = None,
    move_wavs: bool = False,
    auto_rename: bool = True,
    skip_confirm: bool = False,
) -> dict[str, Any]:
    """
    Convert WAV files to MP3 non-interactively.

    Args:
        files: List of WAV file paths
        output_dir: Output directory for MP3 files (default: RECORDINGS_DIR)
        move_wavs: Move original WAV files to storage after conversion (default: False)
        auto_rename: Automatically rename MP3 files after conversion (default: True)
        skip_confirm: Skip confirmation prompts (default: False)

    Returns:
        Dictionary containing conversion results
    """
    ffmpeg_available, error_msg = check_ffmpeg_available()
    if not ffmpeg_available:
        raise RuntimeError(f"ffmpeg not available: {error_msg}")

    audio_files = [Path(f) if isinstance(f, str) else f for f in files]

    for af in audio_files:
        if not af.exists():
            raise FileNotFoundError(f"Audio file not found: {af}")
        if af.suffix.lower() not in AUDIO_EXTENSIONS:
            raise ValueError(
                f"File is not a supported audio format: {af} (allowed: {AUDIO_EXTENSIONS})"
            )

    if not audio_files:
        raise ValueError("No audio files provided")

    if output_dir is None:
        output_dir = Path(RECORDINGS_DIR)
    elif isinstance(output_dir, str):
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    infos = collect_audio_file_infos(audio_files)
    print_audio_file_list(infos, show_total=True)
    print(f"[dim]Output directory: {output_dir}[/dim]")

    if not skip_confirm:
        from rich.prompt import Confirm

        if not Confirm.ask(f"Convert {len(audio_files)} file(s) to MP3?"):
            return {"status": "cancelled"}

    print("\n[bold]Converting files...[/bold]")
    start_time = time.time()
    successful_conversions = []
    failed_conversions = []

    with create_audio_progress(show_pct=True) as progress:
        task = progress.add_task(
            "[cyan]Converting audio files...", total=len(audio_files)
        )

        for af in audio_files:
            try:
                file_size_mb = af.stat().st_size / (1024 * 1024)
                progress.update(
                    task,
                    description=f"[cyan]Converting {af.name} ({file_size_mb:.1f} MB)...[/cyan]",
                )

                output_path = convert_audio_to_mp3(af, output_dir)

                if auto_rename:
                    output_path = rename_mp3_after_conversion(output_path)

                successful_conversions.append((af, output_path))
                progress.update(
                    task,
                    advance=1,
                    description=f"[green]✅ Converted {af.name}[/green]",
                )

            except Exception as e:
                failed_conversions.append((af, str(e)))
                log_error(
                    "AUDIO_CONVERSION",
                    f"Failed to convert {af.name}: {e}",
                    exception=e,
                )
                progress.update(
                    task, advance=1, description=f"[red]❌ Failed {af.name}[/red]"
                )

    elapsed_time = time.time() - start_time

    print("\n[bold green]✅ Conversion Complete![/bold green]")
    print(
        f"[green]Successfully converted: {len(successful_conversions)}/{len(audio_files)} files[/green]"
    )
    print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")

    moved_count = 0
    if move_wavs and successful_conversions:
        print("\n[bold]Moving audio files to storage...[/bold]")
        moved_count, _failed, _skipped = post_convert_backup_and_cleanup(
            successful_conversions,
            delete_originals_if_already_backed_up=True,
            kind="wav",
        )

    return {
        "status": "completed",
        "successful": len(successful_conversions),
        "failed": len(failed_conversions),
        "moved": moved_count if move_wavs else 0,
        "conversions": [(str(w), str(m)) for w, m in successful_conversions],
        "errors": [{"file": str(w), "error": e} for w, e in failed_conversions],
    }
