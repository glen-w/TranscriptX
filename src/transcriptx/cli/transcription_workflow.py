"""
Transcription Workflow Module for TranscriptX CLI.

This module contains the WhisperX transcription workflow that was previously
embedded in the main CLI. It provides a clean, reusable interface for
running audio transcription with proper error handling and user feedback.

Key Features:
- Interactive audio file selection
- WhisperX service management
- Transcription execution with progress tracking
- Optional post-transcription analysis
- Integration with centralized path utilities
"""

import os
import sys
from pathlib import Path
from typing import Any

import questionary
from rich import print

from transcriptx.core import (
    get_available_modules,
    get_default_modules,
    run_analysis_pipeline,
)
from transcriptx.core.pipeline.target_resolver import TranscriptRef
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.utils.error_handling import graceful_exit
from transcriptx.cli.speaker_utils import (
    SpeakerGateDecision,
    check_speaker_gate,
    check_speaker_identification_status,
    run_speaker_identification_for_transcript,
)

# Import CLI utilities
from .file_selection_utils import select_audio_for_whisperx_transcription
from .analysis_utils import (
    select_analysis_mode,
    apply_analysis_mode_settings,
    apply_analysis_mode_settings_non_interactive,
    filter_modules_by_mode,
)
from .transcription_common import transcribe_with_whisperx
from transcriptx.cli.transcription_utils_compose import (
    check_whisperx_compose_service,
    start_whisperx_compose_service,
    wait_for_whisperx_service,
)

logger = get_logger()


def _has_hf_token(config: object | None) -> bool:
    token = ""
    if config and hasattr(config, "transcription"):
        token = getattr(config.transcription, "huggingface_token", "") or ""
    if not token:
        token = os.getenv("TRANSCRIPTX_HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN") or ""
    return bool(token.strip())


def run_transcription_workflow() -> None:
    """
    Run the complete WhisperX transcription workflow.

    This function orchestrates the entire transcription process:
    1. Audio file selection
    2. WhisperX service management
    3. Transcription execution
    4. Optional post-transcription analysis

    Returns:
        None: Results are saved to disk and user is guided through options
    """
    with graceful_exit():
        _run_transcription_workflow_impl()


def _run_transcription_workflow_impl() -> None:
    """Internal implementation of the transcription workflow."""
    try:
        # Integrated WhisperX transcription workflow
        print("\n[bold cyan]🎤 Transcribe with WhisperX[/bold cyan]")

        # Get configuration
        config = get_config()

        # Now allow file selection (supports multiple files)
        audio_files = select_audio_for_whisperx_transcription()
        if not audio_files:
            return
        if isinstance(audio_files, (str, Path)):
            audio_files = [Path(audio_files)]

        # Handle single file selection
        if len(audio_files) == 1:
            audio_file = audio_files[0]
            # Ensure WhisperX service is available before transcription
            if not check_whisperx_compose_service():
                if not start_whisperx_compose_service():
                    log_error("CLI", "Failed to start WhisperX service")
                    return
                if not wait_for_whisperx_service(timeout=60):
                    log_error("CLI", "WhisperX service did not become ready")
                    return

            # Transcribe the audio file using shared transcription function
            print(f"\n[bold]Transcribing with WhisperX:[/bold] {audio_file.name}")
            logger.info(f"Starting WhisperX transcription for audio: {audio_file}")
            result = transcribe_with_whisperx(audio_file, config)

            if not result:
                log_error("CLI", f"WhisperX returned no result for {audio_file}")
                print("\n[red]❌ WhisperX transcription failed.[/red]")
                return

            print(f"\n[green]✅ Transcription completed! File saved to: {result}[/green]")
            logger.info(f"WhisperX transcription completed successfully for: {audio_file}")

            # Ask if user wants to analyze the transcript (only for single file)
            if questionary.confirm(
                "Transcription completed! Would you like to analyze the transcript?"
            ).ask():
                _run_post_transcription_analysis(result, skip_confirm=True)
        else:
            # Handle multiple file selection - transcribe all without asking for analysis
            print(f"\n[bold]Transcribing {len(audio_files)} files with WhisperX[/bold]")
            logger.info(f"Starting batch WhisperX transcription for {len(audio_files)} audio files")
            
            successful_transcriptions = []
            failed_transcriptions = []
            
            for idx, audio_file in enumerate(audio_files, 1):
                if not check_whisperx_compose_service():
                    if not start_whisperx_compose_service():
                        log_error("CLI", "Failed to start WhisperX service")
                        failed_transcriptions.append(audio_file.name)
                        continue
                    if not wait_for_whisperx_service(timeout=60):
                        log_error("CLI", "WhisperX service did not become ready")
                        failed_transcriptions.append(audio_file.name)
                        continue
                print(f"\n[bold][{idx}/{len(audio_files)}] Transcribing:[/bold] {audio_file.name}")
                logger.info(f"Starting WhisperX transcription for audio [{idx}/{len(audio_files)}]: {audio_file}")
                
                try:
                    result = transcribe_with_whisperx(audio_file, config)
                    
                    if not result:
                        log_error("CLI", f"WhisperX returned no result for {audio_file}")
                        print(f"[red]❌ Transcription failed for: {audio_file.name}[/red]")
                        failed_transcriptions.append(audio_file.name)
                    else:
                        print(f"[green]✅ [{idx}/{len(audio_files)}] Completed: {audio_file.name}[/green]")
                        logger.info(f"WhisperX transcription completed successfully for: {audio_file}")
                        successful_transcriptions.append((audio_file.name, result))
                except Exception as e:
                    log_error("CLI", f"Error transcribing {audio_file}: {e}", exception=e)
                    print(f"[red]❌ Error transcribing {audio_file.name}: {e}[/red]")
                    failed_transcriptions.append(audio_file.name)
            
            # Summary
            print(f"\n[bold]Transcription Summary:[/bold]")
            print(f"[green]✅ Successfully transcribed: {len(successful_transcriptions)} file(s)[/green]")
            if failed_transcriptions:
                print(f"[red]❌ Failed: {len(failed_transcriptions)} file(s)[/red]")
                for failed_file in failed_transcriptions:
                    print(f"  - {failed_file}")
            
            # Don't ask for analysis when multiple files are selected
            print("\n[dim]Batch transcription completed. Use the analysis menu to analyze transcripts individually.[/dim]")

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")


def _run_post_transcription_analysis(
    transcript_path: str, *, skip_confirm: bool = False
) -> None:
    """
    Run analysis on the newly transcribed file.

    Args:
        transcript_path: Path to the transcribed transcript file
    """
    try:
        # Select analysis mode
        non_interactive = os.environ.get("PYTEST_CURRENT_TEST") or not sys.stdin.isatty()
        if non_interactive:
            analysis_mode = "quick"
            apply_analysis_mode_settings_non_interactive(analysis_mode)
        else:
            analysis_mode = select_analysis_mode()
            apply_analysis_mode_settings(analysis_mode)

        force_non_interactive = os.environ.get("PYTEST_CURRENT_TEST") or not sys.stdin.isatty()
        decision, status = check_speaker_gate(
            transcript_path, force_non_interactive=bool(force_non_interactive)
        )
        if decision == SpeakerGateDecision.SKIP:
            return

        skip_speaker_mapping = True
        if decision == SpeakerGateDecision.IDENTIFY:
            success, updated_path = run_speaker_identification_for_transcript(
                transcript_path,
                batch_mode=False,
                from_gate=True,
            )
            if success:
                transcript_path = updated_path
                status = check_speaker_identification_status(transcript_path)
                if status.is_complete or status.total_count == 0:
                    skip_speaker_mapping = False
                else:
                    # Offer to proceed or rerun speaker identification
                    while True:
                        speaker_gate_mode = get_config().workflow.speaker_gate.mode
                        choices = [
                            "🔄 Rerun speaker identification",
                            "⏭️ Cancel analysis",
                        ]
                        if speaker_gate_mode != "enforce":
                            choices.insert(1, "✅ Proceed with analysis anyway")
                        choice = questionary.select(
                            "Speaker identification is incomplete. What would you like to do?",
                            choices=choices,
                        ).ask()

                        if choice == "🔄 Rerun speaker identification":
                            # Rerun speaker identification
                            success, updated_path = run_speaker_identification_for_transcript(
                                transcript_path,
                                batch_mode=False,
                                from_gate=True,
                            )
                            if success:
                                transcript_path = updated_path
                                status = check_speaker_identification_status(transcript_path)
                                if status.is_complete or status.total_count == 0:
                                    skip_speaker_mapping = False
                                    break  # Exit loop, proceed with analysis
                                # Still incomplete, loop will ask again
                            else:
                                # User cancelled speaker identification, ask what to do
                                if speaker_gate_mode == "enforce":
                                    return
                                if not questionary.confirm(
                                    "Speaker identification was cancelled. Proceed with analysis anyway?"
                                ).ask():
                                    return
                                break  # Exit loop, proceed with incomplete mapping
                        elif choice == "✅ Proceed with analysis anyway":
                            break  # Exit loop, proceed with incomplete mapping
                        else:  # Cancel analysis
                            return
            else:
                if get_config().workflow.speaker_gate.mode == "enforce":
                    return
                if not questionary.confirm(
                    "Speaker identification was cancelled. Proceed with analysis anyway?"
                ).ask():
                    return
        else:
            # User explicitly chose to proceed without mapping.
            skip_speaker_mapping = True

        # Run ALL analysis modules
        print(
            f"\n[bold]Running all analysis modules on:[/bold] {Path(transcript_path).name}"
        )
        logger.info(
            f"Starting full analysis pipeline for transcribed file: {transcript_path}"
        )

        if not skip_confirm:
            if not questionary.confirm("Proceed with full analysis?").ask():
                return

        # Get all available modules
        all_modules = get_default_modules([transcript_path])
        try:
            run_analysis_pipeline(
                transcript_path=transcript_path,
                selected_modules=all_modules,
                skip_speaker_mapping=skip_speaker_mapping,
                persist=False,
            )
            print(
                f"\n[green]✅ Analysis completed! Results saved to: {transcript_path}[/green]"
            )
            logger.info(
                f"Analysis pipeline completed successfully for: {transcript_path}"
            )
        except Exception as e:
            log_error(
                "CLI",
                f"Analysis pipeline failed for transcribed file {transcript_path}: {e}",
                exception=e,
            )
            print(f"\n[red]❌ Analysis failed: {e}[/red]")
    except KeyboardInterrupt:
        print("\n[cyan]Analysis cancelled. Returning to main menu.[/cyan]")


def run_transcription_non_interactive(
    audio_file: Path | str,
    engine: str = "auto",
    analyze: bool = False,
    analysis_mode: str = "quick",
    analysis_modules: list[str] | None = None,
    skip_confirm: bool = False,
) -> dict[str, Any]:
    """
    Run transcription workflow non-interactively with provided parameters.

    Args:
        audio_file: Path to audio file
        engine: Transcription engine (auto or whisperx)
        analyze: Run analysis after transcription (default: False)
        analysis_mode: Analysis mode if analyze is True - 'quick' or 'full' (default: 'quick')
        analysis_modules: List of module names for analysis or None for all (default: None/all)
        skip_confirm: Skip confirmation prompts (default: False)

    Returns:
        Dictionary containing transcription results and optional analysis results

    Raises:
        FileNotFoundError: If audio file doesn't exist
        ValueError: If invalid parameters provided
    """
    # Convert to Path if string
    if isinstance(audio_file, str):
        audio_file = Path(audio_file)

    # Validate audio file exists
    if not audio_file.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_file}")

    # Validate analysis mode if analyze is True
    if analyze and analysis_mode not in ["quick", "full"]:
        raise ValueError(
            f"Invalid analysis mode: {analysis_mode}. Must be 'quick' or 'full'"
        )

    # Normalize engine selection
    engine_value = (engine or "auto").strip().lower()
    if engine_value not in ("auto", "whisperx"):
        raise ValueError(
            f"Invalid engine: {engine}. Must be 'auto' or 'whisperx'"
        )

    # Resolve engine for auto mode (fail fast if unavailable)
    if engine_value == "auto":
        if not check_whisperx_compose_service():
            return {
                "status": "failed",
                "error": (
                    "WhisperX container is not running. Start it with: "
                    "docker-compose -f docker-compose.whisperx.yml --profile whisperx up -d whisperx"
                ),
                "engine": "auto",
            }
        engine_value = "whisperx"

    # Get configuration
    config = get_config()

    # Transcribe the audio file
    print(f"\n[bold]Transcribing with WhisperX:[/bold] {audio_file.name}")
    logger.info(f"Starting WhisperX transcription for audio: {audio_file}")

    diarize_restore = None
    if getattr(config.transcription, "diarize", True) and not _has_hf_token(config):
        if skip_confirm:
            logger.warning(
                "No Hugging Face token set; proceeding without diarization."
            )
            diarize_restore = config.transcription.diarize
            config.transcription.diarize = False
        else:
            from rich.prompt import Confirm

            if not Confirm.ask(
                "No Hugging Face token set. Proceed without diarization?"
            ):
                return {"status": "cancelled"}
            diarize_restore = config.transcription.diarize
            config.transcription.diarize = False

    if not skip_confirm:
        from rich.prompt import Confirm

        if not Confirm.ask("Proceed with transcription?"):
            return {"status": "cancelled"}

    try:
        result = transcribe_with_whisperx(
            audio_file, config, prompt_for_diarization=False
        )
    finally:
        if diarize_restore is not None:
            config.transcription.diarize = diarize_restore

    if not result:
        log_error("CLI", f"WhisperX returned no result for {audio_file}")
        print("\n[red]❌ WhisperX transcription failed.[/red]")
        return {"status": "failed", "error": "WhisperX returned no result"}

    print(f"\n[green]✅ Transcription completed! File saved to: {result}[/green]")
    logger.info(f"WhisperX transcription completed successfully for: {audio_file}")

    results = {
        "status": "completed",
        "audio_file": str(audio_file),
        "transcript_file": result,
        "engine": engine_value,
    }

    # Run analysis if requested
    if analyze:
        try:
            # Get available modules
            available_modules = get_available_modules()
            default_modules = get_default_modules([transcript_path])

            # Determine modules to use
            if analysis_modules is None:
                selected_modules = default_modules
            elif (
                isinstance(analysis_modules, str) and analysis_modules.lower() == "all"
            ):
                selected_modules = default_modules
            else:
                # Validate module names
                invalid_modules = [
                    m for m in analysis_modules if m not in available_modules
                ]
                if invalid_modules:
                    raise ValueError(
                        f"Invalid module names: {', '.join(invalid_modules)}. Available modules: {', '.join(available_modules)}"
                    )
                selected_modules = analysis_modules

            # Apply analysis mode settings
            apply_analysis_mode_settings_non_interactive(analysis_mode, None)

            # Filter modules based on analysis mode
            filtered_modules = filter_modules_by_mode(selected_modules, analysis_mode)

            print(f"\n[bold]Running analysis on:[/bold] {Path(result).name}")
            print(f"[dim]Mode: {analysis_mode}[/dim]")
            print(f"[dim]Modules: {', '.join(filtered_modules)}[/dim]")
            logger.info(f"Starting analysis pipeline for transcribed file: {result}")

            if not skip_confirm:
                from rich.prompt import Confirm

                if not Confirm.ask("Proceed with analysis?"):
                    return results

            # Run analysis pipeline
            analysis_results = run_analysis_pipeline(
                target=TranscriptRef(path=result),
                selected_modules=filtered_modules,
                skip_speaker_mapping=True,
                persist=False,
            )

            print(f"\n[green]✅ Analysis completed! Results saved to: {result}[/green]")
            logger.info(f"Analysis pipeline completed successfully for: {result}")

            results["analysis"] = {
                "status": "completed",
                "modules_run": analysis_results.get("modules_run", []),
                "errors": analysis_results.get("errors", []),
            }

        except Exception as e:
            log_error(
                "CLI",
                f"Analysis pipeline failed for transcribed file {result}: {e}",
                exception=e,
            )
            print(f"\n[red]❌ Analysis failed: {e}[/red]")
            results["analysis"] = {
                "status": "failed",
                "error": str(e),
            }

    return results
