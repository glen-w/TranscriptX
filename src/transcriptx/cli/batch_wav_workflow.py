"""
Batch WAV Processing Workflow Module for TranscriptX CLI.

This module provides a comprehensive batch processing workflow that automates
the pipeline from WAV files to transcribed transcripts with diarization,
automatic type detection, and tag extraction. After processing, users can
optionally perform batch speaker identification and batch analysis pipeline
for all transcripts.

Key Features:
- Automatic discovery of WAV files in a folder
- Conversion to MP3
- Transcription with WhisperX (includes diarization)
- Conversation type detection
- Tag extraction from early segments
- Batch speaker identification for all processed transcripts
- Batch analysis pipeline for all processed transcripts
- Processing state tracking
- Progress tracking and error recovery
"""

from pathlib import Path
from typing import Any, Dict, List

import questionary
from rich import print
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from transcriptx.cli.audio import (
    check_ffmpeg_available,
    move_wav_to_storage,
    backup_wav_after_processing,
    get_mp3_name_for_wav_backup,
    check_wav_backup_exists,
    PYDUB_AVAILABLE,
    assess_audio_noise,
)
from transcriptx.cli.batch_resume import (
    clear_batch_checkpoint,
    complete_batch_checkpoint,
    create_batch_checkpoint,
    resume_batch_processing,
)
from transcriptx.cli.batch_workflows import (
    run_batch_analysis_pipeline,
    run_batch_speaker_identification,
)
from transcriptx.cli.file_discovery import (
    discover_wav_files,
    filter_files_by_size,
    filter_new_files,
    select_files_interactive,
)
from transcriptx.cli.file_processor import process_single_file
from transcriptx.cli.file_selection_utils import (
    select_folder_interactive,
    get_wav_folder_start_path,
    get_recordings_folder_start_path,
)
from transcriptx.cli.processing_state import get_current_transcript_path_from_state
from transcriptx.core.transcription_runtime import (
    check_whisperx_compose_service,
    start_whisperx_compose_service,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.path_utils import resolve_file_path
from transcriptx.utils.error_handling import graceful_exit

logger = get_logger()
console = Console()


def run_batch_wav_workflow() -> None:
    """
    Run the batch WAV processing workflow main entry point.

    This function orchestrates the entire batch processing pipeline:
    1. Folder selection
    2. File discovery
    3. Processing mode selection (auto/interactive)
    4. Batch processing with progress tracking
    5. Summary report
    """
    with graceful_exit():
        _run_batch_wav_workflow_impl()


def _run_batch_wav_workflow_impl() -> None:
    """Internal implementation of the batch WAV workflow."""
    try:
        print("\n[bold cyan]🔄 Batch Process WAV Folder[/bold cyan]")
        print(
            "[dim]Automated pipeline: Convert → Transcribe → Detect Type → Extract Tags[/dim]"
        )

        # Check for incomplete batches and offer resume
        from transcriptx.cli.batch_resume import get_batch_checkpoint

        checkpoint = get_batch_checkpoint()
        if checkpoint and checkpoint.get("status") == "in_progress":
            print(
                f"\n[yellow]⚠️ Found incomplete batch from {checkpoint.get('started_at', 'unknown time')}[/yellow]"
            )
            print(
                f"  Processed: {len(checkpoint.get('processed_files', []))}/{checkpoint.get('total_files', 0)}"
            )
            print(f"  Failed: {len(checkpoint.get('failed_files', []))}")
            if questionary.confirm(
                "Would you like to resume this batch?", default=True
            ).ask():
                # User wants to resume - we'll handle this in batch_process_files
                # For now, just note that resume is requested
                print("[cyan]Resume will be offered when processing starts...[/cyan]")
            else:
                # User doesn't want to resume - clear checkpoint
                from transcriptx.cli.batch_resume import clear_batch_checkpoint

                clear_batch_checkpoint()
                print("[dim]Checkpoint cleared. Starting fresh batch...[/dim]")

        # Check prerequisites
        if not PYDUB_AVAILABLE:
            print("\n[red]❌ pydub is not installed[/red]")
            print(
                "[yellow]Please install pydub to use batch processing features:[/yellow]"
            )
            print("[cyan]  pip install pydub[/cyan]")
            return

        ffmpeg_available, error_msg = check_ffmpeg_available()
        if not ffmpeg_available:
            print(f"\n[red]❌ {error_msg}[/red]")
            print(
                "[yellow]Please install ffmpeg to use batch processing features.[/yellow]"
            )
            return

        # Step 1: Select folder location
        print("\n[bold]Step 1: Select folder containing WAV files[/bold]")
        config = get_config()
        start_path = get_wav_folder_start_path(config)
        location = select_folder_interactive(start_path=start_path)
        if not location:
            print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
            return

        # Step 2: Discover WAV files
        print(f"\n[bold]Step 2: Discovering WAV files in {location}[/bold]")
        wav_files = discover_wav_files(location)

        if not wav_files:
            print(f"\n[yellow]⚠️ No WAV files found in {location}[/yellow]")
            return

        print(f"[green]✅ Found {len(wav_files)} WAV file(s)[/green]")

        # Step 3: Filter new files (not yet processed)
        print("\n[bold]Step 3: Checking processing status...[/bold]")
        new_files = filter_new_files(wav_files)

        if not new_files:
            print(
                f"\n[yellow]⚠️ All {len(wav_files)} WAV files have already been processed.[/yellow]"
            )
            if questionary.confirm("Would you like to reprocess them?").ask():
                new_files = wav_files
            else:
                return

        print(f"[green]✅ {len(new_files)} new file(s) to process[/green]")

        # Step 4: Filter by file size (optional)
        print("\n[bold]Step 4: Filter by file size (optional)[/bold]")
        workflow_config = config.workflow
        max_size_mb = workflow_config.max_size_mb

        size_filter_choice = questionary.select(
            "Filter files by size?",
            choices=[
                "📦 All files",
                f"📄 Small files only (< {max_size_mb} MB)",
                f"💾 Large files only (≥ {max_size_mb} MB)",
            ],
        ).ask()

        if not size_filter_choice or size_filter_choice == "📦 All files":
            size_filtered_files = new_files
        elif size_filter_choice.startswith("📄"):
            size_filtered_files = filter_files_by_size(
                new_files, max_size_mb=max_size_mb
            )
            print(
                f"[green]✅ {len(size_filtered_files)} small file(s) (< {max_size_mb} MB)[/green]"
            )
        else:  # Large files only
            size_filtered_files = filter_files_by_size(
                new_files, min_size_mb=max_size_mb
            )
            print(
                f"[green]✅ {len(size_filtered_files)} large file(s) (≥ {max_size_mb} MB)[/green]"
            )

        if not size_filtered_files:
            print(f"\n[yellow]⚠️ No files match the selected size filter.[/yellow]")
            return

        # Step 5: Select processing mode
        print("\n[bold]Step 5: Select processing mode[/bold]")
        mode_choice = questionary.select(
            "How would you like to process files?",
            choices=[
                "🚀 Automatic (process all files)",
                "✋ Interactive (select files to process)",
                "❌ Cancel",
            ],
        ).ask()

        if not mode_choice or mode_choice == "❌ Cancel":
            print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
            return

        interactive_mode = mode_choice == "✋ Interactive (select files to process)"

        # Step 6: Select files if interactive
        files_to_process = size_filtered_files
        if interactive_mode:
            files_to_process = select_files_interactive(size_filtered_files)
            if not files_to_process:
                print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
                return

        # Step 7: Batch process files
        print(f"\n[bold]Step 6: Processing {len(files_to_process)} file(s)...[/bold]")
        results = batch_process_files(files_to_process)

        # Step 8: Show summary
        _show_summary(results)

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
    except Exception as e:
        log_error(
            "BATCH_WAV", f"Unexpected error in batch WAV workflow: {e}", exception=e
        )
        print(f"\n[red]❌ An unexpected error occurred: {e}[/red]")


def _assess_and_suggest_preprocessing(
    wav_files: List[Path], config: Any, skip_confirm: bool = False
) -> Dict[Path, Dict[str, bool]]:
    """
    Assess audio files and suggest preprocessing steps based on configuration.

    Args:
        wav_files: List of WAV file paths to assess
        config: AudioPreprocessingConfig instance
        skip_confirm: If True, skip user confirmation and return all False for suggest mode steps

    Returns:
        Dictionary mapping file paths to preprocessing decisions
        Format: {Path: {"denoise": bool, "highpass": bool, "normalize": bool, ...}}
    """
    preprocessing_decisions: Dict[Path, Dict[str, bool]] = {}

    # Check global preprocessing mode
    global_mode = config.preprocessing_mode

    if global_mode == "off":
        # No preprocessing for any file
        for wav_file in wav_files:
            preprocessing_decisions[wav_file] = {
                "denoise": False,
                "highpass": False,
                "lowpass": False,
                "bandpass": False,
                "normalize": False,
                "mono": False,
                "resample": False,
            }
        return preprocessing_decisions

    if global_mode == "auto":
        # All steps apply automatically - no decisions needed
        # apply_preprocessing will check if steps are needed and apply them
        # Return empty dict so apply_preprocessing uses auto logic
        return preprocessing_decisions

    # Determine which steps need assessment (global="suggest" or per-step="suggest")
    steps_to_assess: List[str] = []

    if global_mode == "suggest":
        # All steps are in suggest mode
        steps_to_assess = [
            "denoise",
            "highpass",
            "lowpass",
            "bandpass",
            "normalize",
            "mono",
            "resample",
        ]
    else:  # global_mode == "selected"
        # Check which per-step modes are "suggest"
        if config.denoise_mode == "suggest":
            steps_to_assess.append("denoise")
        if config.highpass_mode == "suggest":
            steps_to_assess.append("highpass")
        if config.lowpass_mode == "suggest":
            steps_to_assess.append("lowpass")
        if config.bandpass_mode == "suggest":
            steps_to_assess.append("bandpass")
        if config.normalize_mode == "suggest":
            steps_to_assess.append("normalize")
        if config.convert_to_mono == "suggest":
            steps_to_assess.append("mono")
        if config.downsample == "suggest":
            steps_to_assess.append("resample")

    # If no steps need assessment, return empty decisions (will use config defaults)
    if not steps_to_assess:
        return preprocessing_decisions

    # Assess all files
    print(
        f"\n[bold]Assessing {len(wav_files)} file(s) for preprocessing suggestions...[/bold]"
    )

    assessments = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Assessing files...", total=len(wav_files))

        for wav_file in wav_files:
            progress.update(task, description=f"Assessing {wav_file.name}...")
            assessment = assess_audio_noise(wav_file)
            assessments.append((wav_file, assessment))
            progress.advance(task)

    # Collect suggestions for each file
    files_needing_preprocessing: Dict[str, List[Path]] = {
        "denoise": [],
        "highpass": [],
        "lowpass": [],
        "bandpass": [],
        "normalize": [],
        "mono": [],
        "resample": [],
    }

    for wav_file, assessment in assessments:
        suggested_steps = assessment.get("suggested_steps", [])

        # Check each step that needs assessment
        for step in steps_to_assess:
            should_apply = False

            if step == "denoise" and "denoise" in suggested_steps:
                should_apply = True
            elif step == "highpass" and "highpass" in suggested_steps:
                should_apply = True
            elif step == "normalize" and "normalize" in suggested_steps:
                should_apply = True
            elif step == "mono" and "mono" in suggested_steps:
                should_apply = True
            elif step == "resample" and "resample" in suggested_steps:
                should_apply = True
            # lowpass and bandpass are not suggested by assessment, so they default to False

            if should_apply:
                files_needing_preprocessing[step].append(wav_file)

    # Show summary
    print(f"\n[bold]Preprocessing Assessment Summary:[/bold]")
    print("-" * 80)

    total_suggestions = 0
    for step, files in files_needing_preprocessing.items():
        if files:
            total_suggestions += len(files)
            step_name = {
                "denoise": "Denoising",
                "highpass": "High-pass filter",
                "lowpass": "Low-pass filter",
                "bandpass": "Band-pass filter",
                "normalize": "Normalization",
                "mono": "Mono conversion",
                "resample": "Resampling",
            }.get(step, step)
            print(f"  {step_name}: {len(files)} file(s)")

    if total_suggestions == 0:
        print("  [dim]No preprocessing suggestions for any files.[/dim]")
        # Initialize decisions with all False
        for wav_file in wav_files:
            preprocessing_decisions[wav_file] = {
                "denoise": False,
                "highpass": False,
                "lowpass": False,
                "bandpass": False,
                "normalize": False,
                "mono": False,
                "resample": False,
            }
        return preprocessing_decisions

    # Ask user to confirm (unless skip_confirm is True)
    if skip_confirm:
        print(f"\n[dim]Skipping user confirmation (non-interactive mode).[/dim]")
        print(f"[dim]For 'suggest' mode steps, preprocessing will be skipped.[/dim]")
        # Initialize decisions with all False (skip all suggested steps)
        for wav_file in wav_files:
            preprocessing_decisions[wav_file] = {
                "denoise": False,
                "highpass": False,
                "lowpass": False,
                "bandpass": False,
                "normalize": False,
                "mono": False,
                "resample": False,
            }
        return preprocessing_decisions

    print(
        f"\n[bold]Total: {total_suggestions} preprocessing suggestion(s) across {len(wav_files)} file(s)[/bold]"
    )

    if not questionary.confirm(
        "Apply suggested preprocessing to files?", default=True
    ).ask():
        print("[cyan]Skipping all suggested preprocessing steps.[/cyan]")
        # Initialize decisions with all False
        for wav_file in wav_files:
            preprocessing_decisions[wav_file] = {
                "denoise": False,
                "highpass": False,
                "lowpass": False,
                "bandpass": False,
                "normalize": False,
                "mono": False,
                "resample": False,
            }
        return preprocessing_decisions

    # Store decisions
    for wav_file, assessment in assessments:
        suggested_steps = assessment.get("suggested_steps", [])
        preprocessing_decisions[wav_file] = {
            "denoise": "denoise" in suggested_steps and "denoise" in steps_to_assess,
            "highpass": "highpass" in suggested_steps and "highpass" in steps_to_assess,
            "lowpass": "lowpass" in suggested_steps and "lowpass" in steps_to_assess,
            "bandpass": "bandpass" in suggested_steps and "bandpass" in steps_to_assess,
            "normalize": "normalize" in suggested_steps
            and "normalize" in steps_to_assess,
            "mono": "mono" in suggested_steps and "mono" in steps_to_assess,
            "resample": "resample" in suggested_steps and "resample" in steps_to_assess,
        }

    return preprocessing_decisions


def batch_process_files(
    wav_files: List[Path], skip_confirm: bool = False
) -> Dict[str, Any]:
    """
    Process multiple WAV files through the full pipeline with checkpoint support.

    Args:
        wav_files: List of WAV file paths to process

    Returns:
        Dictionary with processing results
    """
    import uuid

    results = {
        "total_files": len(wav_files),
        "successful": [],
        "failed": [],
        "skipped": [],
    }

    # Check for existing checkpoint
    resume_info = resume_batch_processing(wav_files)
    batch_id = str(uuid.uuid4())

    if resume_info.get("can_resume"):
        # Ask user if they want to resume
        print(f"\n[yellow]Found previous batch checkpoint:[/yellow]")
        print(
            f"  Processed: {resume_info['processed_count']}/{resume_info['total_count']}"
        )
        print(f"  Failed: {resume_info['failed_count']}")
        print(f"  Remaining: {len(resume_info['remaining_files'])}")

        if questionary.confirm("Resume from checkpoint?", default=True).ask():
            wav_files = resume_info["remaining_files"]
            batch_id = resume_info["checkpoint"]["batch_id"]
            results["successful"] = [
                {"file": f} for f in resume_info["checkpoint"]["processed_files"]
            ]
            results["failed"] = resume_info["checkpoint"]["failed_files"]
        else:
            clear_batch_checkpoint()

    # Ensure WhisperX service is running
    print("\n[cyan]Checking WhisperX service...[/cyan]")
    if not check_whisperx_compose_service():
        print("[yellow]WhisperX service is not running. Starting it now...[/yellow]")
        if not start_whisperx_compose_service():
            print(
                "\n[red]❌ Failed to start WhisperX service. Cannot proceed with transcription.[/red]"
            )
            return results

    print("[green]✅ WhisperX service is ready[/green]")

    # Assess files and get preprocessing decisions
    from transcriptx.core.utils.config import get_config

    config = get_config()
    audio_config = config.audio_preprocessing

    preprocessing_decisions: Dict[Path, Dict[str, bool]] = {}

    # Check if we need to assess files
    global_mode = audio_config.preprocessing_mode
    needs_assessment = False

    if global_mode == "off":
        # No preprocessing needed
        pass
    elif global_mode == "auto":
        # All steps apply automatically - no assessment needed
        pass
    elif global_mode == "suggest":
        # All steps need assessment
        needs_assessment = True
    else:  # global_mode == "selected"
        # Check which per-step modes are "suggest"
        if any(
            [
                audio_config.denoise_mode == "suggest",
                audio_config.highpass_mode == "suggest",
                audio_config.lowpass_mode == "suggest",
                audio_config.bandpass_mode == "suggest",
                audio_config.normalize_mode == "suggest",
                audio_config.convert_to_mono == "suggest",
                audio_config.downsample == "suggest",
            ]
        ):
            needs_assessment = True

    if needs_assessment:
        preprocessing_decisions = _assess_and_suggest_preprocessing(
            wav_files, audio_config, skip_confirm=skip_confirm
        )

    # Create initial checkpoint
    create_batch_checkpoint(
        batch_id=batch_id,
        total_files=results["total_files"],
        processed_files=[r["file"] for r in results["successful"]],
        failed_files=results["failed"],
    )

    # Process files with progress tracking
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing WAV files...", total=len(wav_files))

        for wav_file in wav_files:
            try:
                progress.update(
                    task, description=f"[cyan]Processing {wav_file.name}...[/cyan]"
                )

                # Update checkpoint with current file
                create_batch_checkpoint(
                    batch_id=batch_id,
                    total_files=results["total_files"],
                    processed_files=[r["file"] for r in results["successful"]],
                    failed_files=results["failed"],
                    current_file=str(wav_file.resolve()),
                )

                result = process_single_file(wav_file, preprocessing_decisions)

                if result["status"] == "success":
                    results["successful"].append(result)
                    # Update checkpoint
                    create_batch_checkpoint(
                        batch_id=batch_id,
                        total_files=results["total_files"],
                        processed_files=[r["file"] for r in results["successful"]],
                        failed_files=results["failed"],
                    )
                    progress.update(
                        task,
                        advance=1,
                        description=f"[green]✅ Completed {wav_file.name}[/green]",
                    )
                elif result["status"] == "skipped":
                    results["skipped"].append(result)
                    progress.update(
                        task,
                        advance=1,
                        description=f"[yellow]⏭️ Skipped {wav_file.name}[/yellow]",
                    )
                else:
                    results["failed"].append(result)
                    # Update checkpoint
                    create_batch_checkpoint(
                        batch_id=batch_id,
                        total_files=results["total_files"],
                        processed_files=[r["file"] for r in results["successful"]],
                        failed_files=results["failed"],
                    )
                    progress.update(
                        task,
                        advance=1,
                        description=f"[red]❌ Failed {wav_file.name}[/red]",
                    )

            except KeyboardInterrupt:
                logger.info("Batch processing interrupted by user")
                # Checkpoint is already saved
                raise
            except Exception as e:
                log_error("BATCH_WAV", f"Error processing {wav_file}: {e}", exception=e)
                results["failed"].append(
                    {"file": str(wav_file), "status": "error", "error": str(e)}
                )
                # Update checkpoint with failure
                create_batch_checkpoint(
                    batch_id=batch_id,
                    total_files=results["total_files"],
                    processed_files=[r["file"] for r in results["successful"]],
                    failed_files=results["failed"],
                )
                progress.update(task, advance=1)

    # Mark batch as completed
    complete_batch_checkpoint()

    return results


def _show_summary(results: Dict[str, Any], skip_prompts: bool = False) -> None:
    """
    Show processing summary to user.

    Args:
        results: Processing results dictionary
        skip_prompts: Skip interactive prompts (default: False)
    """
    print("\n" + "=" * 60)
    print("[bold green]📊 Batch Processing Summary[/bold green]")
    print("=" * 60)

    total = results["total_files"]
    successful = len(results["successful"])
    failed = len(results["failed"])
    skipped = len(results["skipped"])

    print(f"\n[bold]Total files:[/bold] {total}")
    print(f"[green]✅ Successful:[/green] {successful}")
    print(f"[red]❌ Failed:[/red] {failed}")
    print(f"[yellow]⏭️ Skipped:[/yellow] {skipped}")

    if results["successful"]:
        print("\n[bold green]✅ Successfully Processed:[/bold green]")
        for result in results["successful"]:
            file_name = Path(result["file"]).name
            conv_type = result["steps"].get("detect_type", {}).get("type", "unknown")
            tags = result["steps"].get("extract_tags", {}).get("tags", [])
            tags_str = ", ".join(tags) if tags else "none"
            print(f"  • {file_name}")
            print(f"    Type: {conv_type} | Tags: {tags_str}")

    if results["failed"]:
        print("\n[bold red]❌ Failed:[/bold red]")
        for result in results["failed"]:
            file_name = Path(result["file"]).name
            error = result.get("error", "Unknown error")
            print(f"  • {file_name}: {error}")

    print("\n" + "=" * 60)

    # Prompt user about moving/deleting original WAV files after all processing is complete
    if results["successful"]:
        wav_mp3_pairs = []
        for result in results["successful"]:
            wav_file_path = Path(result["file"])
            # Only include files that still exist and are WAV files
            if wav_file_path.exists() and wav_file_path.suffix.lower() in [
                ".wav",
                ".WAV",
            ]:
                # Get MP3 path from processing result or state
                mp3_path = None
                convert_step = result.get("steps", {}).get("convert", {})
                if convert_step.get("status") == "success":
                    mp3_path_str = convert_step.get("mp3_path")
                    if mp3_path_str:
                        mp3_path = Path(mp3_path_str)
                        # Check if MP3 was renamed by verifying it exists
                        if not mp3_path.exists():
                            # Try to get from processing state (may have been renamed)
                            mp3_name = get_mp3_name_for_wav_backup(wav_file_path)
                            if mp3_name:
                                # Try to find MP3 in recordings directory
                                config = get_config()
                                recordings_dir = get_recordings_folder_start_path(
                                    config
                                )
                                mp3_path = recordings_dir / f"{mp3_name}.mp3"
                                if not mp3_path.exists():
                                    mp3_path = None

                wav_mp3_pairs.append((wav_file_path, mp3_path))

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
                        backed_up_files.append((wav_file, mp3_path, existing_backup))
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

            if skip_prompts:
                should_move_wavs = False
            else:
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
                            # Use centralized backup function with MP3 path (if available)
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

    # Offer batch speaker identification
    if results["successful"]:
        transcript_paths = []
        for result in results["successful"]:
            transcript_path = (
                result["steps"].get("transcribe", {}).get("transcript_path")
            )
            if transcript_path:
                # Resolve path to get current path (handles renamed files)
                try:
                    resolved_path = resolve_transcript_path(transcript_path)
                    transcript_paths.append(resolved_path)
                except FileNotFoundError:
                    # If resolution fails, try processing state
                    current_path = get_current_transcript_path_from_state(
                        transcript_path
                    )
                    if current_path:
                        transcript_paths.append(current_path)
                    else:
                        # Fallback to original path
                        transcript_paths.append(transcript_path)

        if transcript_paths and not skip_prompts:
            print("\n[bold cyan]🗣️ Speaker Identification[/bold cyan]")
            if questionary.confirm(
                f"Would you like to perform speaker identification for {len(transcript_paths)} transcript(s)?"
            ).ask():
                run_batch_speaker_identification(transcript_paths)


def resolve_transcript_path(transcript_path: str) -> str:
    """
    Resolve a transcript path to an existing file.

    This function now uses the unified path resolution system.

    Args:
        transcript_path: Original transcript path (may be just filename or full path)

    Returns:
        Resolved path to existing transcript file

    Raises:
        FileNotFoundError: If transcript file cannot be found
    """
    return resolve_file_path(
        transcript_path, file_type="transcript", validate_state=True
    )


def run_batch_process_non_interactive(
    folder: Path | str,
    size_filter: str = "all",
    files: list[Path] | list[str] | None = None,
    resume: bool = False,
    clear_checkpoint: bool = False,
    move_wavs: bool = False,
    identify_speakers: bool = False,
    analyze: bool = False,
    analysis_mode: str = "quick",
    skip_confirm: bool = False,
) -> dict[str, Any]:
    """
    Run batch WAV processing non-interactively with provided parameters.

    Args:
        folder: Path to folder containing WAV files
        size_filter: Filter by size - 'all', 'small' (<30MB), 'large' (≥30MB) (default: 'all')
        files: List of specific files to process (optional, overrides folder scan)
        resume: Resume from checkpoint if available (default: False)
        clear_checkpoint: Clear existing checkpoint before processing (default: False)
        move_wavs: Move WAV files to storage after processing (default: False)
        identify_speakers: Run speaker identification after processing (default: False)
        analyze: Run analysis pipeline after processing (default: False)
        analysis_mode: Analysis mode if analyze is True (default: 'quick')
        skip_confirm: Skip confirmation prompts (default: False)

    Returns:
        Dictionary containing batch processing results
    """
    # Check prerequisites
    if not PYDUB_AVAILABLE:
        raise RuntimeError(
            "pydub is not installed. Please install pydub to use batch processing features: pip install pydub"
        )

    ffmpeg_available, error_msg = check_ffmpeg_available()
    if not ffmpeg_available:
        raise RuntimeError(f"ffmpeg not available: {error_msg}")

    # Convert folder to Path
    if isinstance(folder, str):
        folder = Path(folder)

    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")

    # Clear checkpoint if requested
    if clear_checkpoint:
        clear_batch_checkpoint()

    # Get files to process
    if files:
        # Use provided files
        wav_files = [Path(f) if isinstance(f, str) else f for f in files]
        # Validate files exist
        for wav_file in wav_files:
            if not wav_file.exists():
                raise FileNotFoundError(f"WAV file not found: {wav_file}")
    else:
        # Discover WAV files in folder
        print(f"\n[bold]Discovering WAV files in {folder}[/bold]")
        wav_files = discover_wav_files(folder)

        if not wav_files:
            print(f"\n[yellow]⚠️ No WAV files found in {folder}[/yellow]")
            return {
                "status": "completed",
                "total_files": 0,
                "successful": [],
                "failed": [],
                "skipped": [],
            }

        print(f"[green]✅ Found {len(wav_files)} WAV file(s)[/green]")

        # Filter new files (not yet processed)
        print("\n[bold]Checking processing status...[/bold]")
        new_files = filter_new_files(wav_files)

        if not new_files:
            print(
                f"\n[yellow]⚠️ All {len(wav_files)} WAV files have already been processed.[/yellow]"
            )
            if not skip_confirm:
                from rich.prompt import Confirm

                if Confirm.ask("Would you like to reprocess them?"):
                    new_files = wav_files
                else:
                    return {
                        "status": "cancelled",
                        "total_files": len(wav_files),
                        "successful": [],
                        "failed": [],
                        "skipped": [],
                    }
            else:
                new_files = wav_files

        print(f"[green]✅ {len(new_files)} new file(s) to process[/green]")
        wav_files = new_files

        # Apply size filter
        from transcriptx.core.utils.config import get_config

        workflow_config = get_config().workflow
        max_size_mb = workflow_config.max_size_mb

        if size_filter == "small":
            wav_files = filter_files_by_size(wav_files, max_size_mb=max_size_mb)
            print(
                f"[green]✅ {len(wav_files)} small file(s) (< {max_size_mb} MB)[/green]"
            )
        elif size_filter == "large":
            wav_files = filter_files_by_size(wav_files, min_size_mb=max_size_mb)
            print(
                f"[green]✅ {len(wav_files)} large file(s) (≥ {max_size_mb} MB)[/green]"
            )

        if not wav_files:
            print(f"\n[yellow]⚠️ No files match the selected size filter.[/yellow]")
            return {
                "status": "completed",
                "total_files": 0,
                "successful": [],
                "failed": [],
                "skipped": [],
            }

    # Handle resume
    if resume:
        resume_info = resume_batch_processing(wav_files)
        if resume_info.get("can_resume"):
            print(f"\n[yellow]Found previous batch checkpoint:[/yellow]")
            print(
                f"  Processed: {resume_info['processed_count']}/{resume_info['total_count']}"
            )
            print(f"  Failed: {resume_info['failed_count']}")
            print(f"  Remaining: {len(resume_info['remaining_files'])}")

            if not skip_confirm:
                from rich.prompt import Confirm

                if Confirm.ask("Resume from checkpoint?", default=True):
                    wav_files = resume_info["remaining_files"]
            else:
                wav_files = resume_info["remaining_files"]

    # Confirm if not skipped
    if not skip_confirm:
        from rich.prompt import Confirm

        if not Confirm.ask(f"Process {len(wav_files)} file(s)?"):
            return {"status": "cancelled"}

    # Process files
    print(f"\n[bold]Processing {len(wav_files)} file(s)...[/bold]")
    results = batch_process_files(wav_files, skip_confirm=skip_confirm)

    # Show summary
    _show_summary(results, skip_prompts=skip_confirm)

    # Handle post-processing options
    if results["successful"]:
        # Move WAV files if requested
        if move_wavs:
            wav_files_to_manage = []
            for result in results["successful"]:
                wav_file_path = Path(result["file"])
                if wav_file_path.exists() and wav_file_path.suffix.lower() in [
                    ".wav",
                    ".WAV",
                ]:
                    wav_files_to_manage.append(wav_file_path)

            if wav_files_to_manage:
                print(f"\n[bold]Moving WAV files to storage...[/bold]")
                moved_count = 0
                failed_count = 0

                for wav_file in wav_files_to_manage:
                    if wav_file.exists():
                        if move_wav_to_storage(wav_file):
                            moved_count += 1
                            print(f"  ✅ Moved {wav_file.name}")
                        else:
                            failed_count += 1
                            print(f"  ❌ Failed to move {wav_file.name}")

        # Run speaker identification if requested
        if identify_speakers:
            transcript_paths = []
            for result in results["successful"]:
                transcript_path = (
                    result["steps"].get("transcribe", {}).get("transcript_path")
                )
                if transcript_path:
                    try:
                        resolved_path = resolve_transcript_path(transcript_path)
                        transcript_paths.append(resolved_path)
                    except FileNotFoundError:
                        current_path = get_current_transcript_path_from_state(
                            transcript_path
                        )
                        if current_path:
                            transcript_paths.append(current_path)
                        else:
                            transcript_paths.append(transcript_path)

            if transcript_paths:
                print(f"\n[bold cyan]🗣️ Speaker Identification[/bold cyan]")
                print(
                    f"[dim]Running speaker identification for {len(transcript_paths)} transcript(s)...[/dim]"
                )
                run_batch_speaker_identification(transcript_paths)

        # Run analysis if requested
        if analyze:
            transcript_paths = []
            for result in results["successful"]:
                transcript_path = (
                    result["steps"].get("transcribe", {}).get("transcript_path")
                )
                if transcript_path:
                    try:
                        resolved_path = resolve_transcript_path(transcript_path)
                        transcript_paths.append(resolved_path)
                    except FileNotFoundError:
                        current_path = get_current_transcript_path_from_state(
                            transcript_path
                        )
                        if current_path:
                            transcript_paths.append(current_path)
                        else:
                            transcript_paths.append(transcript_path)

            if transcript_paths:
                print(f"\n[bold cyan]📊 Analysis Pipeline[/bold cyan]")
                print(
                    f"[dim]Running analysis for {len(transcript_paths)} transcript(s)...[/dim]"
                )
                from transcriptx.cli.analysis_utils import (
                    apply_analysis_mode_settings_non_interactive,
                )

                apply_analysis_mode_settings_non_interactive(analysis_mode, None)
                run_batch_analysis_pipeline(transcript_paths)

    return {
        "status": "completed",
        "total_files": results["total_files"],
        "successful": len(results["successful"]),
        "failed": len(results["failed"]),
        "skipped": len(results["skipped"]),
        "results": results,
    }
