"""
WAV Processing Workflow Module for TranscriptX CLI.

This module provides workflows for processing WAV files:
- Convert single or multiple WAV files to MP3
- Merge multiple WAV files into one MP3 file

Key Features:
- Interactive file selection starting from /Volumes/
- Progress tracking with spinners and time estimates
- Comprehensive error handling
- Integration with audio conversion utilities
"""

import time
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

import questionary
from rich import print
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeRemainingColumn,
)

from transcriptx.cli.audio import (
    convert_wav_to_mp3,
    merge_wav_files,
    check_ffmpeg_available,
    get_audio_duration,
    backup_wav_files_to_storage,
    backup_wav_after_processing,
    check_wav_backup_exists,
    compress_wav_backups,
    assess_audio_noise,
    check_audio_compliance,
    apply_preprocessing,
)
from transcriptx.cli.file_selection_utils import (
    select_wav_files_interactive,
    reorder_files_interactive,
    get_wav_folder_start_path,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.file_rename import (
    rename_mp3_after_conversion,
    extract_date_prefix,
)
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import (
    RECORDINGS_DIR,
    WAV_STORAGE_DIR,
    PREPROCESSING_DIR,
)
from transcriptx.core.utils.performance_estimator import (
    PerformanceEstimator,
    format_time_estimate,
)
from transcriptx.utils.error_handling import graceful_exit

logger = get_logger()
console = Console()


def run_preprocess_single_file(
    file_path: Path,
    output_path: Path | None = None,
    skip_confirm: bool = False,
) -> Dict[str, Any]:
    """
    Run audio preprocessing on a single file (MP3, WAV, or other supported format).

    Args:
        file_path: Path to the audio file.
        output_path: Optional output path. Default: same dir, stem_preprocessed.<ext>.
        skip_confirm: If True, overwrite existing output without asking.

    Returns:
        Dict with status ("ok" | "cancelled" | "failed"), output_path, applied_steps, error.
    """
    result: Dict[str, Any] = {
        "status": "ok",
        "output_path": None,
        "applied_steps": [],
        "error": None,
    }

    file_path = file_path.resolve()
    if not file_path.exists():
        result["status"] = "failed"
        result["error"] = f"File not found: {file_path}"
        return result

    try:
        from pydub import AudioSegment
    except ImportError:
        result["status"] = "failed"
        result["error"] = "pydub is not installed. Install with: pip install pydub"
        return result

    ffmpeg_ok, err = check_ffmpeg_available()
    if not ffmpeg_ok:
        result["status"] = "failed"
        result["error"] = err
        return result

    config = get_config().audio_preprocessing
    suffix = file_path.suffix.lower()
    if output_path is None:
        output_path = file_path.parent / f"{file_path.stem}_preprocessed{suffix}"
    else:
        output_path = output_path.resolve()

    if output_path.exists() and not skip_confirm:
        ok = questionary.confirm(
            f"Overwrite {output_path.name}?", default=False
        ).ask()
        if not ok:
            result["status"] = "cancelled"
            return result

    print(f"[bold]Loading[/bold] {file_path.name}...")
    try:
        audio = AudioSegment.from_file(str(file_path))
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        return result

    preprocessing_decisions = None
    needs_suggest = (
        config.preprocessing_mode == "suggest"
        or config.denoise_mode == "suggest"
        or config.highpass_mode == "suggest"
        or config.lowpass_mode == "suggest"
        or config.bandpass_mode == "suggest"
        or config.normalize_mode == "suggest"
        or config.convert_to_mono == "suggest"
        or config.downsample == "suggest"
    )
    if needs_suggest:
        print("[dim]Assessing audio...[/dim]")
        assessment = assess_audio_noise(file_path)
        preprocessing_decisions = {
            "denoise": "denoise" in assessment["suggested_steps"],
            "highpass": "highpass" in assessment["suggested_steps"],
            "lowpass": "lowpass" in assessment["suggested_steps"],
            "bandpass": "bandpass" in assessment["suggested_steps"],
            "normalize": "normalize" in assessment["suggested_steps"],
            "mono": "mono" in assessment["suggested_steps"],
            "resample": "resample" in assessment["suggested_steps"],
        }

    print("[bold]Applying preprocessing...[/bold]")
    try:
        processed_audio, applied_steps = apply_preprocessing(
            audio, config, progress_callback=None, preprocessing_decisions=preprocessing_decisions
        )
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        return result

    out_ext = output_path.suffix.lower()
    fmt = "mp3" if out_ext == ".mp3" else "wav" if out_ext == ".wav" else out_ext.lstrip(".")
    if fmt == "mp3":
        processed_audio.export(str(output_path), format="mp3", bitrate="192k")
    else:
        processed_audio.export(str(output_path), format=fmt)

    result["output_path"] = output_path
    result["applied_steps"] = applied_steps
    return result


def run_wav_processing_workflow() -> None:
    """
    Run the WAV processing workflow main menu.

    Provides options to convert or merge WAV files with proper error handling.
    """
    with graceful_exit():
        _run_wav_processing_workflow_impl()


def _run_wav_processing_workflow_impl() -> None:
    """Internal implementation of the WAV processing workflow."""
    try:
        print("\n[bold cyan]🎵 Process WAV Files[/bold cyan]")

        # Check ffmpeg availability first
        ffmpeg_available, error_msg = check_ffmpeg_available()
        if not ffmpeg_available:
            print(f"\n[red]❌ {error_msg}[/red]")
            print(
                "[yellow]Please install ffmpeg to use WAV processing features.[/yellow]"
            )
            print("[dim]On macOS: brew install ffmpeg[/dim]")
            print("[dim]On Linux: sudo apt-get install ffmpeg[/dim]")
            return

        # Show submenu
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "〰️ Preprocessing",
                "🔄 Convert WAV to MP3",
                "🔗 Merge WAV Files",
                "🗜️ Compress WAV Backups",
                "❌ Cancel",
            ],
        ).ask()

        if choice == "〰️ Preprocessing":
            _run_preprocessing_workflow()
        elif choice == "🔄 Convert WAV to MP3":
            _run_convert_workflow()
        elif choice == "🔗 Merge WAV Files":
            _run_merge_workflow()
        elif choice == "🗜️ Compress WAV Backups":
            _run_compress_workflow()
        elif choice == "❌ Cancel" or not choice:
            print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
            return

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
    except Exception as e:
        log_error(
            "WAV_PROCESSING",
            f"Unexpected error in WAV processing workflow: {e}",
            exception=e,
        )
        print(f"\n[red]❌ An unexpected error occurred: {e}[/red]")


def _run_preprocessing_workflow() -> None:
    """Run the audio preprocessing workflow."""
    try:
        from transcriptx.core.utils.config import get_config

        try:
            from pydub import AudioSegment
        except ImportError:
            print(
                "\n[red]❌ pydub is not installed. Please install it to use preprocessing features.[/red]"
            )
            return

        print("\n[bold cyan]〰️ Audio Preprocessing[/bold cyan]")
        print(
            "[dim]Optimize audio files for transcription with ASR-safe preprocessing[/dim]"
        )

        # Check dependencies
        ffmpeg_available, error_msg = check_ffmpeg_available()
        if not ffmpeg_available:
            print(f"\n[red]❌ {error_msg}[/red]")
            print(
                "[yellow]Please install ffmpeg to use preprocessing features.[/yellow]"
            )
            return

        # Get config
        config = get_config()
        audio_config = config.audio_preprocessing

        # Step 1: Select WAV files (explore or direct path)
        print("\n[dim]Select WAV files to preprocess[/dim]")
        start_path = get_wav_folder_start_path(config)
        wav_files = select_wav_files_interactive(start_path=start_path)
        if not wav_files:
            print("\n[yellow]⚠️ No WAV files selected. Returning to menu.[/yellow]")
            return

        print(f"\n[bold]Selected {len(wav_files)} file(s) for preprocessing:[/bold]")
        for idx, wav_file in enumerate(wav_files, 1):
            size_mb = wav_file.stat().st_size / (1024 * 1024)
            duration = get_audio_duration(wav_file)
            if duration:
                duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
                print(f"  {idx}. {wav_file.name} ({size_mb:.1f} MB, {duration_str})")
            else:
                print(f"  {idx}. {wav_file.name} ({size_mb:.1f} MB)")

        # Step 3: Assess files
        print("\n[bold]Assessing audio files...[/bold]")
        assessments = []
        skipped_files = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Assessing files...", total=len(wav_files))

            for wav_file in wav_files:
                progress.update(task, description=f"Assessing {wav_file.name}...")

                # Check compliance
                compliance = check_audio_compliance(wav_file, audio_config)
                if (
                    compliance["is_compliant"]
                    and audio_config.skip_if_already_compliant
                ):
                    skipped_files.append((wav_file, "already compliant"))
                    progress.advance(task)
                    continue

                # Assess noise
                assessment = assess_audio_noise(wav_file)
                assessments.append((wav_file, assessment, compliance))
                progress.advance(task)

        # Step 4: Display results
        if skipped_files:
            print(
                f"\n[yellow]⚠️ Skipped {len(skipped_files)} file(s) (already compliant):[/yellow]"
            )
            for wav_file, reason in skipped_files:
                print(f"  • {wav_file.name} ({reason})")

        if not assessments:
            print(
                "\n[cyan]All files are already compliant. No preprocessing needed.[/cyan]"
            )
            return

        print(f"\n[bold]Assessment Results:[/bold]")
        print("-" * 80)
        for wav_file, assessment, compliance in assessments:
            noise_level = assessment["noise_level"]
            noise_emoji = (
                "🟢"
                if noise_level == "low"
                else "🟡" if noise_level == "medium" else "🔴"
            )
            print(f"\n{noise_emoji} {wav_file.name}")
            print(
                f"  Noise Level: {noise_level.upper()} (confidence: {assessment['confidence']:.1%})"
            )
            if assessment["suggested_steps"]:
                print(f"  Suggested Steps: {', '.join(assessment['suggested_steps'])}")
            if compliance["missing_requirements"]:
                print(f"  Missing: {', '.join(compliance['missing_requirements'])}")

        # Step 5: Confirm processing
        if not questionary.confirm(
            f"\nPreprocess {len(assessments)} file(s) with suggested settings?"
        ).ask():
            print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
            return

        # Step 6: Apply preprocessing
        print("\n[bold]Applying preprocessing...[/bold]")
        processed_files = []
        failed_files = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Processing files...", total=len(assessments))

            for wav_file, assessment, compliance in assessments:
                try:
                    progress.update(task, description=f"Processing {wav_file.name}...")

                    # Load audio
                    audio = AudioSegment.from_wav(str(wav_file))

                    # Apply suggested preprocessing based on assessment
                    # Build preprocessing decisions from assessment suggestions
                    preprocessing_decisions: Dict[str, bool] = {
                        "denoise": "denoise" in assessment["suggested_steps"],
                        "highpass": "highpass" in assessment["suggested_steps"],
                        "lowpass": "lowpass" in assessment["suggested_steps"],
                        "bandpass": "bandpass" in assessment["suggested_steps"],
                        "normalize": "normalize" in assessment["suggested_steps"],
                        "mono": "mono" in assessment["suggested_steps"],
                        "resample": "resample" in assessment["suggested_steps"],
                    }

                    # Apply preprocessing with decisions
                    processed_audio, applied_steps = apply_preprocessing(
                        audio, audio_config, None, preprocessing_decisions
                    )

                    # Save processed file (move original to backup, save processed as main)
                    original_path = wav_file

                    # Get original file size before moving
                    original_file_size_mb = original_path.stat().st_size / (1024 * 1024)

                    # Determine backup path in data/backups/wav
                    backup_dir = Path(WAV_STORAGE_DIR)
                    backup_dir.mkdir(parents=True, exist_ok=True)
                    original_backup_path = backup_dir / f"{wav_file.stem}_original.wav"

                    # Check if _original already exists
                    counter = 1
                    while original_backup_path.exists():
                        original_backup_path = (
                            backup_dir / f"{wav_file.stem}_original_{counter}.wav"
                        )
                        counter += 1

                    # Move original to backup directory
                    shutil.move(str(original_path), str(original_backup_path))

                    # Save processed as main file
                    processed_audio.export(str(original_path), format="wav")

                    # Get processed file size
                    processed_file_size_mb = original_path.stat().st_size / (
                        1024 * 1024
                    )

                    # Write JSON sidecar to data/preprocessing/
                    preprocessing_dir = Path(PREPROCESSING_DIR)
                    preprocessing_dir.mkdir(parents=True, exist_ok=True)
                    sidecar_path = (
                        preprocessing_dir / f"{wav_file.stem}_preprocessing.json"
                    )
                    sidecar_data = {
                        "original_file": str(original_backup_path),
                        "processed_file": str(original_path),
                        "assessment": {
                            "noise_level": assessment["noise_level"],
                            "confidence": assessment["confidence"],
                            "suggested_steps": assessment["suggested_steps"],
                            "metrics": assessment["metrics"],
                        },
                        "applied_steps": applied_steps,
                        "before": {
                            "file_size_mb": original_file_size_mb,
                            "channels": audio.channels,
                            "sample_rate": audio.frame_rate,
                        },
                        "after": {
                            "file_size_mb": processed_file_size_mb,
                            "channels": processed_audio.channels,
                            "sample_rate": processed_audio.frame_rate,
                        },
                        "timestamp": datetime.now().isoformat(),
                    }

                    with open(sidecar_path, "w") as f:
                        json.dump(sidecar_data, f, indent=2)

                    processed_files.append((wav_file, applied_steps))
                    progress.advance(task)

                except Exception as e:
                    logger.error(f"Error preprocessing {wav_file}: {e}")
                    log_error(
                        "AUDIO_PREPROCESSING",
                        f"Failed to preprocess {wav_file}: {e}",
                        exception=e,
                    )
                    failed_files.append((wav_file, str(e)))
                    progress.advance(task)

        # Step 7: Summary
        print("\n" + "=" * 80)
        print("[bold green]✅ Preprocessing Complete[/bold green]")
        print("=" * 80)

        if processed_files:
            print(
                f"\n[green]Successfully processed {len(processed_files)} file(s):[/green]"
            )
            for wav_file, steps in processed_files:
                print(f"  • {wav_file.name}")
                if steps:
                    print(f"    Applied: {', '.join(steps)}")
                print(
                    f"    Original moved to: data/backups/wav/{wav_file.stem}_original.wav"
                )
                print(
                    f"    Metadata saved as: data/preprocessing/{wav_file.stem}_preprocessing.json"
                )

        if failed_files:
            print(f"\n[red]Failed to process {len(failed_files)} file(s):[/red]")
            for wav_file, error in failed_files:
                print(f"  • {wav_file.name}: {error}")

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
    except Exception as e:
        log_error(
            "AUDIO_PREPROCESSING",
            f"Unexpected error in preprocessing workflow: {e}",
            exception=e,
        )
        print(f"\n[red]❌ An unexpected error occurred: {e}[/red]")


def _run_convert_workflow() -> None:
    """Run the convert WAV to MP3 workflow."""
    try:
        from transcriptx.core.utils.config import get_config

        print("\n[bold cyan]🔄 Convert WAV to MP3[/bold cyan]")
        print("[dim]Select WAV files to convert[/dim]")

        # Step 1: Select WAV files (explore or direct path)
        config = get_config()
        start_path = get_wav_folder_start_path(config)
        wav_files = select_wav_files_interactive(start_path=start_path)
        if not wav_files:
            print("\n[yellow]⚠️ No WAV files selected. Returning to menu.[/yellow]")
            return

        if len(wav_files) == 0:
            print("\n[red]❌ No valid WAV files selected.[/red]")
            return

        # Show selected files
        print(f"\n[bold]Selected {len(wav_files)} file(s) for conversion:[/bold]")
        total_size_mb = 0
        for idx, wav_file in enumerate(wav_files, 1):
            size_mb = wav_file.stat().st_size / (1024 * 1024)
            total_size_mb += size_mb
            duration = get_audio_duration(wav_file)
            if duration:
                duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
                print(f"  {idx}. {wav_file.name} ({size_mb:.1f} MB, {duration_str})")
            else:
                print(f"  {idx}. {wav_file.name} ({size_mb:.1f} MB)")

        print(f"\n[dim]Total size: {total_size_mb:.1f} MB[/dim]")

        # Confirm conversion
        if not questionary.confirm(f"\nConvert {len(wav_files)} file(s) to MP3?").ask():
            print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
            return

        # Set up output directory
        output_dir = Path(RECORDINGS_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Convert files with progress tracking
        print(f"\n[bold]Converting files...[/bold]")
        print(f"[dim]Output directory: {output_dir}[/dim]")

        start_time = time.time()
        successful_conversions = []
        failed_conversions = []

        # Use Rich Progress for file-by-file progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "[cyan]Converting WAV files...", total=len(wav_files)
            )

            for idx, wav_file in enumerate(wav_files, 1):
                try:
                    # Update progress
                    file_size_mb = wav_file.stat().st_size / (1024 * 1024)
                    progress.update(
                        task,
                        description=f"[cyan]Converting {wav_file.name} ({file_size_mb:.1f} MB)...[/cyan]",
                    )

                    # Convert file
                    output_path = convert_wav_to_mp3(wav_file, output_dir)

                    successful_conversions.append((wav_file, output_path))
                    progress.update(
                        task,
                        advance=1,
                        description=f"[green]✅ Converted {wav_file.name}[/green]",
                    )

                except Exception as e:
                    failed_conversions.append((wav_file, str(e)))
                    log_error(
                        "WAV_CONVERSION",
                        f"Failed to convert {wav_file.name}: {e}",
                        exception=e,
                    )
                    progress.update(
                        task,
                        advance=1,
                        description=f"[red]❌ Failed {wav_file.name}[/red]",
                    )

        elapsed_time = time.time() - start_time

        # Show summary
        print(f"\n[bold green]✅ Conversion Complete![/bold green]")
        print(
            f"[green]Successfully converted: {len(successful_conversions)}/{len(wav_files)} files[/green]"
        )
        print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")
        print(f"[dim]Output directory: {output_dir}[/dim]")

        if successful_conversions:
            print(f"\n[bold]Converted files:[/bold]")
            for wav_file, output_path in successful_conversions:
                print(f"  ✅ {wav_file.name} → {output_path.name}")

        if failed_conversions:
            print(f"\n[yellow]⚠️ Failed conversions:[/yellow]")
            for wav_file, error in failed_conversions:
                print(f"  ❌ {wav_file.name}: {error}")

        # Offer rename option for each successfully converted file
        if successful_conversions:
            renamed_paths = []
            for wav_file, output_path in successful_conversions:
                renamed_path = rename_mp3_after_conversion(output_path)
                renamed_paths.append((wav_file, renamed_path))

            # Update successful_conversions with renamed paths
            successful_conversions = renamed_paths

            # Automatically backup WAV files after conversion (before deletion prompt)
            # This ensures backup happens regardless of user's deletion choice
            backed_up_count = 0
            already_backed_up_count = 0
            for wav_file, mp3_path in successful_conversions:
                if wav_file.exists() and wav_file.suffix.lower() == ".wav":
                    # Check if already backed up
                    existing_backup = check_wav_backup_exists(
                        wav_file, mp3_path=mp3_path
                    )
                    if not existing_backup:
                        # Backup WAV file (don't delete original - user will be prompted later)
                        backup_path = backup_wav_after_processing(
                            wav_file,
                            mp3_path=mp3_path,
                            target_name=None,
                            delete_original=False,  # Keep original, user will decide later
                        )
                        if backup_path:
                            backed_up_count += 1
                            logger.info(
                                f"Automatically backed up {wav_file.name} to {backup_path.name}"
                            )
                    else:
                        already_backed_up_count += 1
                        logger.debug(
                            f"{wav_file.name} already backed up as {existing_backup.name}"
                        )

            if backed_up_count > 0 or already_backed_up_count > 0:
                if backed_up_count > 0:
                    print(
                        f"[dim]✅ Automatically backed up {backed_up_count} WAV file(s) to storage[/dim]"
                    )
                if already_backed_up_count > 0:
                    print(
                        f"[dim]ℹ️  {already_backed_up_count} WAV file(s) were already backed up[/dim]"
                    )

        # Prompt user about moving/deleting original WAV files after all conversions are complete
        if successful_conversions:
            wav_mp3_pairs = [
                (wav_file, mp3_path) for wav_file, mp3_path in successful_conversions
            ]
            if wav_mp3_pairs:
                print(f"\n[bold cyan]📁 WAV File Management[/bold cyan]")
                print(
                    f"[dim]You have {len(wav_mp3_pairs)} original WAV file(s) that can be moved to storage.[/dim]"
                )

                # Check which files have already been backed up
                backed_up_files = []
                not_backed_up_files = []
                for wav_file, mp3_path in wav_mp3_pairs:
                    if wav_file.exists():
                        existing_backup = check_wav_backup_exists(
                            wav_file, mp3_path=mp3_path
                        )
                        if existing_backup:
                            backed_up_files.append(
                                (wav_file, mp3_path, existing_backup)
                            )
                        else:
                            not_backed_up_files.append((wav_file, mp3_path))

                # Inform user about backup status
                if backed_up_files:
                    print(
                        f"\n[green]✅ {len(backed_up_files)} file(s) already backed up:[/green]"
                    )
                    for wav_file, mp3_path, backup_path in backed_up_files:
                        print(f"  • {wav_file.name} → {backup_path.name}")

                if not_backed_up_files:
                    print(
                        f"\n[yellow]⚠️  {len(not_backed_up_files)} file(s) not yet backed up:[/yellow]"
                    )
                    for wav_file, mp3_path in not_backed_up_files:
                        print(f"  • {wav_file.name}")

                should_move_wavs = questionary.confirm(
                    f"Move {len(wav_mp3_pairs)} WAV file(s) to storage and delete originals?",
                    default=False,
                ).ask()

                if should_move_wavs:
                    print(f"\n[bold]Moving WAV files to storage...[/bold]")
                    moved_count = 0
                    failed_count = 0
                    skipped_count = 0

                    for wav_file, mp3_path in wav_mp3_pairs:
                        if wav_file.exists():  # Check if file still exists
                            # Check if already backed up
                            existing_backup = check_wav_backup_exists(
                                wav_file, mp3_path=mp3_path
                            )
                            if existing_backup:
                                # File already backed up, just delete original
                                try:
                                    wav_file.unlink()
                                    moved_count += 1
                                    skipped_count += 1
                                    print(
                                        f"  ✅ Deleted {wav_file.name} (already backed up as {existing_backup.name})"
                                    )
                                except Exception as e:
                                    failed_count += 1
                                    print(f"  ❌ Failed to delete {wav_file.name}: {e}")
                            else:
                                # Use centralized backup function with renamed MP3 path
                                backup_path = backup_wav_after_processing(
                                    wav_file,
                                    mp3_path=mp3_path,
                                    target_name=None,
                                    delete_original=True,
                                )
                                if backup_path:
                                    moved_count += 1
                                    print(
                                        f"  ✅ Moved {wav_file.name} → {backup_path.name}"
                                    )
                                else:
                                    failed_count += 1
                                    print(f"  ❌ Failed to move {wav_file.name}")
                        else:
                            print(f"  ⚠️  {wav_file.name} no longer exists, skipping")

                    if moved_count > 0:
                        if skipped_count > 0:
                            print(
                                f"\n[green]✅ Successfully processed {moved_count} WAV file(s) ({skipped_count} already backed up, {moved_count - skipped_count} newly backed up)[/green]"
                            )
                        else:
                            print(
                                f"\n[green]✅ Successfully moved {moved_count} WAV file(s) to storage[/green]"
                            )
                    if failed_count > 0:
                        print(
                            f"\n[yellow]⚠️  Failed to process {failed_count} WAV file(s)[/yellow]"
                        )
                else:
                    print(f"\n[cyan]Keeping original WAV files[/cyan]")

    except KeyboardInterrupt:
        print("\n[cyan]Conversion cancelled. Returning to menu.[/cyan]")
    except Exception as e:
        log_error("WAV_CONVERSION", f"Error in convert workflow: {e}", exception=e)
        print(f"\n[red]❌ Conversion failed: {e}[/red]")


def _run_merge_workflow() -> None:
    """Run the merge WAV files workflow."""
    try:
        print("\n[bold cyan]🔗 Merge WAV Files[/bold cyan]")
        print("[dim]Select WAV files to merge[/dim]")

        # Step 1: Select WAV files (explore or direct path, need at least 2)
        wav_files = select_wav_files_interactive(start_path=Path("/Volumes/"))
        if not wav_files:
            print("\n[yellow]⚠️ No WAV files selected. Returning to menu.[/yellow]")
            return

        if len(wav_files) < 2:
            print("\n[red]❌ Please select at least 2 WAV files to merge.[/red]")
            return

        # Step 3: Allow user to reorder files
        print("\n[bold cyan]📋 File Order[/bold cyan]")
        print("[dim]You can reorder the files to control the merge sequence.[/dim]")
        wav_files = reorder_files_interactive(wav_files)
        if not wav_files:
            print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
            return

        # Show selected files and calculate total duration
        print(f"\n[bold]Selected {len(wav_files)} file(s) for merging:[/bold]")
        total_size_mb = 0
        total_duration = 0.0

        for idx, wav_file in enumerate(wav_files, 1):
            size_mb = wav_file.stat().st_size / (1024 * 1024)
            total_size_mb += size_mb
            duration = get_audio_duration(wav_file)
            if duration:
                total_duration += duration
                duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
                print(f"  {idx}. {wav_file.name} ({size_mb:.1f} MB, {duration_str})")
            else:
                print(f"  {idx}. {wav_file.name} ({size_mb:.1f} MB)")

        if total_duration > 0:
            total_duration_str = (
                f"{int(total_duration // 60)}:{int(total_duration % 60):02d}"
            )
            print(f"\n[dim]Total size: {total_size_mb:.1f} MB[/dim]")
            print(f"[dim]Estimated total duration: {total_duration_str}[/dim]")
        else:
            print(f"\n[dim]Total size: {total_size_mb:.1f} MB[/dim]")

        # Prompt for output filename with date prefix from earliest file
        date_prefix = extract_date_prefix(wav_files[0]) if wav_files else ""
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

        # Ensure .mp3 extension
        if not output_filename.endswith(".mp3"):
            output_filename += ".mp3"

        # Set up output path
        output_dir = Path(RECORDINGS_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_filename

        # Check if file exists
        if output_path.exists():
            if not questionary.confirm(
                f"File {output_filename} already exists. Overwrite?"
            ).ask():
                print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
                return

        # Confirm merge
        if not questionary.confirm(
            f"\nMerge {len(wav_files)} files into {output_filename}?"
        ).ask():
            print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
            return

        # Backup WAV files to storage before merging
        print(f"\n[bold]Backing up WAV files to storage...[/bold]")
        try:
            # Extract base name from output filename (without .mp3 extension)
            base_name = Path(output_filename).stem
            backup_paths = backup_wav_files_to_storage(wav_files, base_name=base_name)
            if backup_paths:
                print(
                    f"[green]✅ Backed up {len(backup_paths)} file(s) to wav storage[/green]"
                )
                # Use backup paths for merging since originals were moved
                wav_files = backup_paths
            else:
                print(
                    f"[yellow]⚠️ Warning: No files were backed up. Continuing with merge...[/yellow]"
                )
        except Exception as e:
            log_error("WAV_BACKUP", f"Error backing up WAV files: {e}", exception=e)
            print(
                f"[yellow]⚠️ Warning: Backup failed: {e}. Continuing with merge...[/yellow]"
            )
            # Continue with merge even if backup fails

        # Merge files with progress tracking
        print(f"\n[bold]Merging files...[/bold]")
        print(f"[dim]Output file: {output_path}[/dim]")

        start_time = time.time()

        # Use Rich Progress for merge operation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Merging WAV files...", total=len(wav_files))

            def progress_callback(current: int, total: int, message: str):
                progress.update(task, advance=1, description=f"[cyan]{message}[/cyan]")

            try:
                output_path = merge_wav_files(
                    wav_files, output_path, progress_callback=progress_callback
                )

                progress.update(
                    task,
                    completed=len(wav_files),
                    description="[green]✅ Merge completed![/green]",
                )

            except Exception as e:
                progress.update(task, description=f"[red]❌ Merge failed: {e}[/red]")
                raise

        elapsed_time = time.time() - start_time

        # Show summary
        print(f"\n[bold green]✅ Merge Complete![/bold green]")
        print(
            f"[green]Successfully merged {len(wav_files)} files into: {output_path.name}[/green]"
        )
        print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")
        print(f"[dim]Output file: {output_path}[/dim]")

        if total_duration > 0:
            total_duration_str = (
                f"{int(total_duration // 60)}:{int(total_duration % 60):02d}"
            )
            print(f"[dim]Total duration: {total_duration_str}[/dim]")

    except KeyboardInterrupt:
        print("\n[cyan]Merge cancelled. Returning to menu.[/cyan]")
    except Exception as e:
        log_error("WAV_MERGE", f"Error in merge workflow: {e}", exception=e)
        print(f"\n[red]❌ Merge failed: {e}[/red]")


def _run_compress_workflow() -> None:
    """Run the compress WAV backups workflow."""
    try:
        print("\n[bold cyan]🗜️ Compress WAV Backups[/bold cyan]")
        print("[dim]Compress WAV files in data/backups/wav into zip archives[/dim]")

        # Check if WAV storage directory exists
        wav_storage_dir = Path(WAV_STORAGE_DIR)
        if not wav_storage_dir.exists():
            print(
                f"\n[yellow]⚠️ WAV storage directory does not exist: {wav_storage_dir}[/yellow]"
            )
            print("[cyan]No WAV files to compress. Returning to menu.[/cyan]")
            return

        # Find all .wav files (exclude .zip files)
        wav_files = [
            f
            for f in wav_storage_dir.iterdir()
            if f.is_file() and f.suffix.lower() == ".wav"
        ]

        if not wav_files:
            print(f"\n[yellow]⚠️ No WAV files found in {wav_storage_dir}[/yellow]")
            print("[cyan]Returning to menu.[/cyan]")
            return

        # Calculate total size
        total_size = sum(f.stat().st_size for f in wav_files)
        total_size_mb = total_size / (1024 * 1024)

        # Show summary
        print(f"\n[bold]Found {len(wav_files)} WAV file(s) to compress[/bold]")
        print(f"[dim]Total size: {total_size_mb:.1f} MB[/dim]")
        print(f"[dim]Location: {wav_storage_dir}[/dim]")

        # Estimate space savings (WAV files typically compress to 10-20% of original size)
        estimated_compressed_mb = total_size_mb * 0.15  # Conservative estimate
        estimated_savings_mb = total_size_mb - estimated_compressed_mb
        print(
            f"[dim]Estimated compressed size: ~{estimated_compressed_mb:.1f} MB[/dim]"
        )
        print(f"[dim]Estimated space savings: ~{estimated_savings_mb:.1f} MB[/dim]")

        # Show time estimate
        try:
            estimator = PerformanceEstimator()
            estimate = estimator.estimate_compression_time(
                total_size_mb=total_size_mb, file_count=len(wav_files)
            )
            if estimate.get("estimated_seconds") is not None:
                estimate_str = format_time_estimate(estimate)
                print(f"[dim]Estimated time: {estimate_str}[/dim]")
        except Exception:
            pass  # Don't fail if estimation fails

        # Confirm compression
        if not questionary.confirm(f"\nCompress {len(wav_files)} WAV file(s)?").ask():
            print("\n[cyan]Cancelled. Returning to menu.[/cyan]")
            return

        # Ask about deleting originals
        delete_originals = questionary.confirm(
            "Delete original WAV files after successful compression?", default=False
        ).ask()

        if delete_originals:
            print(
                "[yellow]⚠️ Original WAV files will be deleted after compression[/yellow]"
            )

        # Compress files with progress tracking
        print(f"\n[bold]Compressing files...[/bold]")

        start_time = time.time()

        # Use Rich Progress for compression operation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(
                "[cyan]Compressing WAV files...", total=len(wav_files)
            )

            def progress_callback(current: int, total: int, message: str):
                progress.update(task, advance=1, description=f"[cyan]{message}[/cyan]")

            try:
                zip_paths, files_compressed, zip_count = compress_wav_backups(
                    delete_originals=delete_originals,
                    progress_callback=progress_callback,
                )

                progress.update(
                    task,
                    completed=len(wav_files),
                    description="[green]✅ Compression completed![/green]",
                )

            except Exception as e:
                progress.update(
                    task, description=f"[red]❌ Compression failed: {e}[/red]"
                )
                raise

        elapsed_time = time.time() - start_time

        # Show summary
        print(f"\n[bold green]✅ Compression Complete![/bold green]")
        print(
            f"[green]Successfully compressed {files_compressed} file(s) into {zip_count} zip file(s)[/green]"
        )
        print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")

        if zip_paths:
            print(f"\n[bold]Created zip files:[/bold]")
            for zip_path in zip_paths:
                zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
                print(f"  ✅ {zip_path.name} ({zip_size_mb:.1f} MB)")

        if delete_originals:
            print(f"\n[green]✅ Original WAV files have been deleted[/green]")
        else:
            print(f"\n[cyan]Original WAV files have been preserved[/cyan]")

    except KeyboardInterrupt:
        print("\n[cyan]Compression cancelled. Returning to menu.[/cyan]")
    except Exception as e:
        log_error("WAV_COMPRESS", f"Error in compress workflow: {e}", exception=e)
        print(f"\n[red]❌ Compression failed: {e}[/red]")


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
    # Check ffmpeg availability
    ffmpeg_available, error_msg = check_ffmpeg_available()
    if not ffmpeg_available:
        raise RuntimeError(f"ffmpeg not available: {error_msg}")

    # Convert files to Path objects
    wav_files = [Path(f) if isinstance(f, str) else f for f in files]

    # Validate files exist
    for wav_file in wav_files:
        if not wav_file.exists():
            raise FileNotFoundError(f"WAV file not found: {wav_file}")
        if wav_file.suffix.lower() != ".wav":
            raise ValueError(f"File is not a WAV file: {wav_file}")

    if not wav_files:
        raise ValueError("No WAV files provided")

    # Set up output directory
    if output_dir is None:
        output_dir = Path(RECORDINGS_DIR)
    elif isinstance(output_dir, str):
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Show selected files
    print(f"\n[bold]Selected {len(wav_files)} file(s) for conversion:[/bold]")
    total_size_mb = 0
    for idx, wav_file in enumerate(wav_files, 1):
        size_mb = wav_file.stat().st_size / (1024 * 1024)
        total_size_mb += size_mb
        duration = get_audio_duration(wav_file)
        if duration:
            duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
            print(f"  {idx}. {wav_file.name} ({size_mb:.1f} MB, {duration_str})")
        else:
            print(f"  {idx}. {wav_file.name} ({size_mb:.1f} MB)")

    print(f"\n[dim]Total size: {total_size_mb:.1f} MB[/dim]")
    print(f"[dim]Output directory: {output_dir}[/dim]")

    # Confirm if not skipped
    if not skip_confirm:
        from rich.prompt import Confirm

        if not Confirm.ask(f"Convert {len(wav_files)} file(s) to MP3?"):
            return {"status": "cancelled"}

    # Convert files with progress tracking
    print(f"\n[bold]Converting files...[/bold]")
    start_time = time.time()
    successful_conversions = []
    failed_conversions = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Converting WAV files...", total=len(wav_files))

        for wav_file in wav_files:
            try:
                file_size_mb = wav_file.stat().st_size / (1024 * 1024)
                progress.update(
                    task,
                    description=f"[cyan]Converting {wav_file.name} ({file_size_mb:.1f} MB)...[/cyan]",
                )

                output_path = convert_wav_to_mp3(wav_file, output_dir)

                # Rename if requested
                if auto_rename:
                    output_path = rename_mp3_after_conversion(output_path)

                successful_conversions.append((wav_file, output_path))
                progress.update(
                    task,
                    advance=1,
                    description=f"[green]✅ Converted {wav_file.name}[/green]",
                )

            except Exception as e:
                failed_conversions.append((wav_file, str(e)))
                log_error(
                    "WAV_CONVERSION",
                    f"Failed to convert {wav_file.name}: {e}",
                    exception=e,
                )
                progress.update(
                    task, advance=1, description=f"[red]❌ Failed {wav_file.name}[/red]"
                )

    elapsed_time = time.time() - start_time

    # Show summary
    print(f"\n[bold green]✅ Conversion Complete![/bold green]")
    print(
        f"[green]Successfully converted: {len(successful_conversions)}/{len(wav_files)} files[/green]"
    )
    print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")

    # Move WAV files if requested
    moved_count = 0
    if move_wavs and successful_conversions:
        print(f"\n[bold]Moving WAV files to storage...[/bold]")
        for wav_file, mp3_path in successful_conversions:
            if wav_file.exists():
                # Check if already backed up
                existing_backup = check_wav_backup_exists(wav_file, mp3_path=mp3_path)
                if existing_backup:
                    # File already backed up, just delete original
                    try:
                        wav_file.unlink()
                        moved_count += 1
                        print(f"  ✅ Deleted {wav_file.name} (already backed up)")
                    except Exception as e:
                        print(f"  ❌ Failed to delete {wav_file.name}: {e}")
                else:
                    # Backup and delete
                    backup_path = backup_wav_after_processing(
                        wav_file,
                        mp3_path=mp3_path,
                        target_name=None,
                        delete_original=True,
                    )
                    if backup_path:
                        moved_count += 1
                        print(f"  ✅ Moved {wav_file.name} → {backup_path.name}")
                    else:
                        print(f"  ❌ Failed to move {wav_file.name}")

    return {
        "status": "completed",
        "successful": len(successful_conversions),
        "failed": len(failed_conversions),
        "moved": moved_count if move_wavs else 0,
        "conversions": [(str(w), str(m)) for w, m in successful_conversions],
        "errors": [{"file": str(w), "error": e} for w, e in failed_conversions],
    }


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
    # Check ffmpeg availability
    ffmpeg_available, error_msg = check_ffmpeg_available()
    if not ffmpeg_available:
        raise RuntimeError(f"ffmpeg not available: {error_msg}")

    # Convert files to Path objects
    wav_files = [Path(f) if isinstance(f, str) else f for f in files]

    # Validate files
    if len(wav_files) < 2:
        raise ValueError("At least 2 WAV files are required for merging")

    for wav_file in wav_files:
        if not wav_file.exists():
            raise FileNotFoundError(f"WAV file not found: {wav_file}")
        if wav_file.suffix.lower() != ".wav":
            raise ValueError(f"File is not a WAV file: {wav_file}")

    # Set up output path
    if output_dir is None:
        output_dir = Path(RECORDINGS_DIR)
    elif isinstance(output_dir, str):
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate output filename if not provided
    if not output_file:
        date_prefix = extract_date_prefix(wav_files[0]) if wav_files else ""
        output_file = (
            f"{date_prefix}merged.mp3"
            if date_prefix
            else f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        )

    # Ensure .mp3 extension
    if not output_file.endswith(".mp3"):
        output_file += ".mp3"

    output_path = output_dir / output_file

    # Check if file exists
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Output file already exists: {output_path}. Use --overwrite to overwrite."
        )

    # Show selected files
    print(f"\n[bold]Selected {len(wav_files)} file(s) for merging:[/bold]")
    total_size_mb = 0
    total_duration = 0.0
    for idx, wav_file in enumerate(wav_files, 1):
        size_mb = wav_file.stat().st_size / (1024 * 1024)
        total_size_mb += size_mb
        duration = get_audio_duration(wav_file)
        if duration:
            total_duration += duration
            duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
            print(f"  {idx}. {wav_file.name} ({size_mb:.1f} MB, {duration_str})")
        else:
            print(f"  {idx}. {wav_file.name} ({size_mb:.1f} MB)")

    if total_duration > 0:
        total_duration_str = (
            f"{int(total_duration // 60)}:{int(total_duration % 60):02d}"
        )
        print(f"\n[dim]Total size: {total_size_mb:.1f} MB[/dim]")
        print(f"[dim]Estimated total duration: {total_duration_str}[/dim]")
    else:
        print(f"\n[dim]Total size: {total_size_mb:.1f} MB[/dim]")

    print(f"[dim]Output file: {output_path}[/dim]")

    # Confirm if not skipped
    if not skip_confirm:
        from rich.prompt import Confirm

        if not Confirm.ask(f"Merge {len(wav_files)} files into {output_file}?"):
            return {"status": "cancelled"}

    # Backup WAV files if requested
    if backup_wavs:
        print(f"\n[bold]Backing up WAV files to storage...[/bold]")
        try:
            # Extract base name from output filename (without .mp3 extension)
            base_name = Path(output_file).stem
            backup_paths = backup_wav_files_to_storage(wav_files, base_name=base_name)
            if backup_paths:
                print(
                    f"[green]✅ Backed up {len(backup_paths)} file(s) to wav storage[/green]"
                )
                wav_files = backup_paths
            else:
                print(
                    f"[yellow]⚠️ Warning: No files were backed up. Continuing with merge...[/yellow]"
                )
        except Exception as e:
            log_error("WAV_BACKUP", f"Error backing up WAV files: {e}", exception=e)
            print(
                f"[yellow]⚠️ Warning: Backup failed: {e}. Continuing with merge...[/yellow]"
            )

    # Merge files
    print(f"\n[bold]Merging files...[/bold]")
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Merging WAV files...", total=len(wav_files))

        def progress_callback(current: int, total: int, message: str):
            progress.update(task, advance=1, description=f"[cyan]{message}[/cyan]")

        try:
            output_path = merge_wav_files(
                wav_files, output_path, progress_callback=progress_callback
            )
            progress.update(
                task,
                completed=len(wav_files),
                description="[green]✅ Merge completed![/green]",
            )
        except Exception as e:
            progress.update(task, description=f"[red]❌ Merge failed: {e}[/red]")
            raise

    elapsed_time = time.time() - start_time

    print(f"\n[bold green]✅ Merge Complete![/bold green]")
    print(
        f"[green]Successfully merged {len(wav_files)} files into: {output_path.name}[/green]"
    )
    print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")

    return {
        "status": "completed",
        "output_file": str(output_path),
        "files_merged": len(wav_files),
        "backed_up": backup_wavs,
    }


def run_wav_compress_non_interactive(
    delete_originals: bool = False,
    storage_dir: Path | str | None = None,
    skip_confirm: bool = False,
) -> dict[str, Any]:
    """
    Compress WAV files in backups directory into zip archives non-interactively.

    Args:
        delete_originals: Delete original WAV files after successful compression (default: False)
        storage_dir: Custom WAV storage directory path (default: data/backups/wav)
        skip_confirm: Skip confirmation prompts (default: False)

    Returns:
        Dictionary containing compression results
    """
    # Determine storage directory
    if storage_dir is None:
        wav_storage_dir = Path(WAV_STORAGE_DIR)
    elif isinstance(storage_dir, str):
        wav_storage_dir = Path(storage_dir)
    else:
        wav_storage_dir = storage_dir

    if not wav_storage_dir.exists():
        raise FileNotFoundError(
            f"WAV storage directory does not exist: {wav_storage_dir}"
        )

    # Find all .wav files
    wav_files = [
        f
        for f in wav_storage_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ".wav"
    ]

    if not wav_files:
        print(f"\n[yellow]⚠️ No WAV files found in {wav_storage_dir}[/yellow]")
        return {
            "status": "completed",
            "files_compressed": 0,
            "zip_count": 0,
            "zip_files": [],
        }

    # Calculate total size
    total_size = sum(f.stat().st_size for f in wav_files)
    total_size_mb = total_size / (1024 * 1024)

    print(f"\n[bold]Found {len(wav_files)} WAV file(s) to compress[/bold]")
    print(f"[dim]Total size: {total_size_mb:.1f} MB[/dim]")
    print(f"[dim]Location: {wav_storage_dir}[/dim]")

    # Estimate space savings
    estimated_compressed_mb = total_size_mb * 0.15
    estimated_savings_mb = total_size_mb - estimated_compressed_mb
    print(f"[dim]Estimated compressed size: ~{estimated_compressed_mb:.1f} MB[/dim]")
    print(f"[dim]Estimated space savings: ~{estimated_savings_mb:.1f} MB[/dim]")

    # Confirm if not skipped
    if not skip_confirm:
        from rich.prompt import Confirm

        if not Confirm.ask(f"Compress {len(wav_files)} WAV file(s)?"):
            return {"status": "cancelled"}

        if delete_originals:
            if not Confirm.ask(
                "Delete original WAV files after successful compression?"
            ):
                delete_originals = False

    # Compress files
    print(f"\n[bold]Compressing files...[/bold]")
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Compressing WAV files...", total=len(wav_files))

        def progress_callback(current: int, total: int, message: str):
            progress.update(task, advance=1, description=f"[cyan]{message}[/cyan]")

        try:
            zip_paths, files_compressed, zip_count = compress_wav_backups(
                delete_originals=delete_originals, progress_callback=progress_callback
            )
            progress.update(
                task,
                completed=len(wav_files),
                description="[green]✅ Compression completed![/green]",
            )
        except Exception as e:
            progress.update(task, description=f"[red]❌ Compression failed: {e}[/red]")
            raise

    elapsed_time = time.time() - start_time

    print(f"\n[bold green]✅ Compression Complete![/bold green]")
    print(
        f"[green]Successfully compressed {files_compressed} file(s) into {zip_count} zip file(s)[/green]"
    )
    print(f"[dim]Time taken: {timedelta(seconds=int(elapsed_time))}[/dim]")

    if zip_paths:
        print(f"\n[bold]Created zip files:[/bold]")
        for zip_path in zip_paths:
            zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
            print(f"  ✅ {zip_path.name} ({zip_size_mb:.1f} MB)")

    return {
        "status": "completed",
        "files_compressed": files_compressed,
        "zip_count": zip_count,
        "zip_files": [str(z) for z in zip_paths],
        "deleted_originals": delete_originals,
    }
