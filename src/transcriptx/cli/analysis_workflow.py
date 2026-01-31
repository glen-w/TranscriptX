"""
Analysis Workflow Module for TranscriptX CLI.

This module contains the single-file analysis workflow that was previously
embedded in the main CLI. It provides a clean, reusable interface for
running transcript analysis with proper error handling and user feedback.

Key Features:
- Interactive transcript file selection
- Analysis mode and module selection
- Progress tracking and error handling
- Post-analysis menu with file opening options
- Integration with centralized path utilities
"""

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

import questionary
from rich import print

from transcriptx.core import (
    get_available_modules,
    get_default_modules,
    run_analysis_pipeline,
)
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.path_utils import get_transcript_dir
from transcriptx.utils.error_handling import graceful_exit
from transcriptx.utils.progress import ProgressConfig, process_spinner, resource_monitor
from transcriptx.cli.speaker_utils import (
    SpeakerGateDecision,
    check_speaker_gate,
    check_speaker_identification_status,
    run_speaker_identification_for_transcript,
)

# Import CLI utilities
from .exit_codes import CliExit
from .file_selection_utils import select_transcript_files_interactive
from .analysis_utils import (
    select_analysis_modules,
    select_analysis_mode,
    apply_analysis_mode_settings,
    apply_analysis_mode_settings_non_interactive,
    filter_modules_by_mode,
)

logger = get_logger()


def run_single_analysis_workflow(
    transcript_path: Path | str | None = None,
    skip_speaker_gate: bool = False,
) -> None:
    """
    Run the complete single-file analysis workflow.

    This function orchestrates the entire analysis process:
    1. File selection (if transcript_path not provided)
    2. Analysis mode and module selection
    3. Analysis execution with progress tracking
    4. Post-analysis menu with file opening options

    Args:
        transcript_path: Optional path to transcript file. If provided, skips file selection.
        skip_speaker_gate: Skip speaker identification gate if already handled upstream.

    Returns:
        None: Results are saved to disk and user is guided through options
    """
    with graceful_exit():
        _run_analysis_workflow_impl(
            transcript_path=transcript_path,
            skip_speaker_gate=skip_speaker_gate,
        )


def _run_analysis_workflow_impl(
    transcript_path: Path | str | None = None,
    skip_speaker_gate: bool = False,
) -> None:
    """
    Internal implementation of the analysis workflow.

    Args:
        transcript_path: Optional path to transcript file. If provided, skips file selection.
        skip_speaker_gate: Skip speaker identification gate if already handled upstream.
    """
    try:
        # Analyze workflow
        print("\n[bold cyan]📊 Analyze Transcript[/bold cyan]")

        # Use provided transcript path or select interactively
        if transcript_path:
            # Convert to Path if string
            if isinstance(transcript_path, str):
                transcript_path = Path(transcript_path)

            # Validate transcript file exists
            if not transcript_path.exists():
                print(f"\n[red]❌ Transcript file not found: {transcript_path}[/red]")
                return

            transcript_files = [transcript_path]
            print(f"\n[dim]Using transcript: {transcript_path.name}[/dim]")
        else:
            # Select transcript files interactively (supports multi-select)
            transcript_files = select_transcript_files_interactive()
            if not transcript_files or len(transcript_files) == 0:
                print(
                    "\n[yellow]⚠️ No transcript files selected. Returning to main menu.[/yellow]"
                )
                return

        # Select analysis mode
        analysis_mode = select_analysis_mode()
        apply_analysis_mode_settings(analysis_mode)

        # Select analysis modules
        modules = select_analysis_modules()

        # Filter modules based on analysis mode
        filtered_modules = filter_modules_by_mode(modules, analysis_mode)

        # Handle multiple transcripts using batch analysis pipeline
        if len(transcript_files) > 1:
            print(
                f"\n[bold]Selected {len(transcript_files)} transcripts for analysis[/bold]"
            )
            logger.info(
                f"Starting batch analysis workflow for {len(transcript_files)} transcripts"
            )

            # Confirm analysis
            print(f"\n[bold]Selected modules:[/bold] {', '.join(filtered_modules)}")
            print(f"[bold]Transcripts to analyze:[/bold]")
            for idx, tf in enumerate(transcript_files, 1):
                print(f"  {idx}. {tf.name}")

            if not questionary.confirm("Proceed with batch analysis?").ask():
                return

            # Use batch analysis pipeline for multiple transcripts
            # Pass pre-selected mode and modules to avoid duplicate prompts
            from transcriptx.cli.batch_workflows import run_batch_analysis_pipeline

            transcript_paths = [str(tf) for tf in transcript_files]
            run_batch_analysis_pipeline(
                transcript_paths,
                analysis_mode=analysis_mode,
                selected_modules=filtered_modules,
                skip_speaker_gate=skip_speaker_gate,
            )
            return

        # Single transcript - use existing single-file workflow
        transcript_file = transcript_files[0]
        print(f"\n[bold]Analyzing transcript:[/bold] {transcript_file.name}")
        logger.info(f"Starting analysis workflow for transcript: {transcript_file}")

        skip_speaker_mapping = True
        if not skip_speaker_gate:
            decision, status = check_speaker_gate(str(transcript_file))
            if decision == SpeakerGateDecision.SKIP:
                return
            if decision == SpeakerGateDecision.IDENTIFY:
                success, updated_path = run_speaker_identification_for_transcript(
                    str(transcript_file),
                    batch_mode=False,
                )
                if success:
                    transcript_file = Path(updated_path)
                    status = check_speaker_identification_status(str(transcript_file))
                    if status.is_complete or status.total_count == 0:
                        skip_speaker_mapping = False
                    else:
                        # Offer to proceed or rerun speaker identification
                        while True:
                            choice = questionary.select(
                                "Speaker identification is incomplete. What would you like to do?",
                                choices=[
                                    "🔄 Rerun speaker identification",
                                    "✅ Proceed with analysis anyway",
                                    "⏭️ Cancel analysis",
                                ],
                            ).ask()
                            
                            if choice == "🔄 Rerun speaker identification":
                                # Rerun speaker identification
                                success, updated_path = run_speaker_identification_for_transcript(
                                    str(transcript_file),
                                    batch_mode=False,
                                )
                                if success:
                                    transcript_file = Path(updated_path)
                                    status = check_speaker_identification_status(str(transcript_file))
                                    if status.is_complete or status.total_count == 0:
                                        skip_speaker_mapping = False
                                        break  # Exit loop, proceed with analysis
                                    # Still incomplete, loop will ask again
                                else:
                                    # User cancelled speaker identification, ask what to do
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
                    if not questionary.confirm(
                        "Speaker identification was cancelled. Proceed with analysis anyway?"
                    ).ask():
                        return
            else:
                skip_speaker_mapping = True

        # Confirm analysis
        print(f"\n[bold]Selected modules:[/bold] {', '.join(filtered_modules)}")

        if not questionary.confirm("Proceed with analysis?").ask():
            return

        # Run analysis with enhanced progress tracking
        try:
            # Get analysis mode to determine timeout
            from transcriptx.core.utils.config import get_config

            config = get_config()
            analysis_mode = config.analysis.analysis_mode
            workflow_config = config.workflow

            # Set timeout based on analysis mode: use config values
            if analysis_mode == "full":
                timeout_seconds = workflow_config.timeout_full_seconds
            else:
                timeout_seconds = workflow_config.timeout_quick_seconds

            # Set up progress tracking
            progress_config = ProgressConfig(
                update_interval=workflow_config.update_interval,
                show_percentage=True,
                show_memory=True,
                show_time_remaining=True,
                show_speed=True,
                timeout=timeout_seconds,
                timeout_warn_only=True,  # Log warning instead of crashing pipeline
                graceful_exit=True,
            )

            with process_spinner(
                "Running analysis pipeline", progress_config
            ) as tracker:
                with resource_monitor("Analysis pipeline"):
                    results = run_analysis_pipeline(
                        target=str(transcript_file),
                        selected_modules=filtered_modules,
                        skip_speaker_mapping=skip_speaker_mapping,
                        persist=False,
                    )

                    # Update progress to completion
                    tracker.update(100 - tracker.current)

            # Show analysis status from state
            try:
                from transcriptx.core.utils.state_utils import get_analysis_history

                analysis_status = get_analysis_history(str(transcript_file))
                if analysis_status:
                    status = analysis_status.get("status", "unknown")
                    modules_run = analysis_status.get("modules_run", [])
                    modules_failed = analysis_status.get("modules_failed", [])

                    if status == "completed":
                        print("\n[green]✅ Analysis completed successfully![/green]")
                        print(f"[dim]Modules run: {', '.join(modules_run)}[/dim]")
                    elif status == "partial":
                        print(
                            f"\n[yellow]⚠️ Analysis completed partially ({len(modules_run)}/{len(analysis_status.get('modules_requested', []))} modules)[/yellow]"
                        )
                        if modules_failed:
                            print(
                                f"[dim]Failed modules: {', '.join(modules_failed)}[/dim]"
                            )
                    elif status == "failed":
                        print(f"\n[red]❌ Analysis failed[/red]")
                    else:
                        print(f"\n[yellow]⚠️ Analysis status: {status}[/yellow]")

                    if results["errors"]:
                        print(f"[yellow]Errors: {len(results['errors'])}[/yellow]")
                        for error in results["errors"]:
                            print(f"  • {error}")
            except Exception as e:
                # Fallback to original behavior if state lookup fails
                logger.debug(f"Could not get analysis status from state: {e}")
                if results["errors"]:
                    print(
                        f"\n[yellow]⚠️ Analysis completed with {len(results['errors'])} errors.[/yellow]"
                    )
                    for error in results["errors"]:
                        print(f"  • {error}")
                else:
                    print("\n[green]✅ Analysis completed successfully![/green]")

            output_dir = get_transcript_dir(str(transcript_file))
            print(f"Output directory: {results.get('output_dir')}")
            logger.info(f"Analysis completed for {transcript_file}")

            # Show post-analysis menu
            _show_post_analysis_menu(transcript_file, results)

        except CliExit as e:
            # CliExit is used for controlled exits, re-raise it
            raise
        except Exception as e:
            log_error(
                "CLI",
                f"Analysis workflow failed for {transcript_file}: {e}",
                exception=e,
            )
            print(f"\n[red]❌ Analysis failed: {e}[/red]")

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")


def _show_post_analysis_menu(transcript_file: Path, results: dict[str, Any]) -> None:
    """
    Show the post-analysis menu with file opening options.

    Args:
        transcript_file: Path to the analyzed transcript file
        results: Analysis results dictionary
    """
    transcript_path_str = str(transcript_file)
    analyzed_base = transcript_file.stem
    output_dir = results.get("output_dir")
    if not output_dir:
        output_dir = get_transcript_dir(transcript_path_str)
    analyzed_dir = Path(output_dir)
    stats_dir = analyzed_dir / "stats"
    summary_dir = stats_dir / "summary"
    html_path = analyzed_dir / f"{analyzed_base}_comprehensive_summary.html"
    txt_path = summary_dir / f"{analyzed_base}_comprehensive_summary.txt"
    outputs_folder = analyzed_dir

    # Only show viewer option if result is defined and not None
    while True:
        # Show analysis status if available
        try:
            from transcriptx.core.utils.state_utils import (
                get_analysis_history,
                get_missing_modules,
            )

            analysis_status = get_analysis_history(transcript_path_str)
            if analysis_status:
                status = analysis_status.get("status", "unknown")
                modules_requested = analysis_status.get("modules_requested", [])
                missing_modules = get_missing_modules(
                    transcript_path_str, modules_requested
                )

                if missing_modules:
                    menu_choices = [
                        "🔄 Re-run failed/missing modules",
                        "📂 Open outputs folder",
                        "🌐 Open HTML summary",
                        "📑 Open stats.txt",
                    ]
                else:
                    menu_choices = [
                        "📂 Open outputs folder",
                        "🌐 Open HTML summary",
                        "📑 Open stats.txt",
                    ]
            else:
                menu_choices = [
                    "📂 Open outputs folder",
                    "🌐 Open HTML summary",
                    "📑 Open stats.txt",
                ]
        except Exception:
            menu_choices = [
                "📂 Open outputs folder",
                "🌐 Open HTML summary",
                "📑 Open stats.txt",
            ]

        menu_choices += [
            "🔄 Run another analysis module",
            "🏠 Return to main menu",
            "🚪 Exit",
        ]
        next_action = questionary.select(
            "What would you like to do next?",
            choices=menu_choices,
        ).ask()

        if next_action == "🔄 Re-run failed/missing modules":
            # Re-run only failed/missing modules
            try:
                from transcriptx.core.utils.state_utils import get_missing_modules

                missing_modules = get_missing_modules(
                    transcript_path_str, analysis_status.get("modules_requested", [])
                )
                if missing_modules:
                    print(
                        f"\n[cyan]Re-running modules: {', '.join(missing_modules)}[/cyan]"
                    )
                    run_analysis_pipeline(
                        target=transcript_path_str,
                        selected_modules=missing_modules,
                        skip_speaker_mapping=skip_speaker_mapping,
                        persist=False,
                    )
                    # Restart menu to show updated status
                    continue
                else:
                    print("\n[yellow]No missing modules to re-run[/yellow]")
            except Exception as e:
                logger.error(f"Error re-running modules: {e}")
                print(f"\n[red]Error re-running modules: {e}[/red]")
        elif next_action == "📂 Open outputs folder":
            _open_file_or_folder(outputs_folder)
        elif next_action == "🌐 Open HTML summary":
            _open_html_summary(html_path)
        elif next_action == "📑 Open stats.txt":
            _open_stats_file(txt_path)
        elif next_action == "🔄 Run another analysis module":
            # Restart the analysis workflow
            logger.info("User requested to run another analysis module")
            _run_analysis_workflow_impl()
            return
        elif next_action == "🏠 Return to main menu":
            return
        elif next_action == "🚪 Exit":
            print("\n[green]👋 Thanks for using TranscriptX![green]")
            logger.info("User exited TranscriptX")
            from .exit_codes import exit_success

            exit_success()


def _open_file_or_folder(path: Path) -> None:
    """Open a file or folder using the system default application."""
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False)
        elif sys.platform == "win32":
            os.startfile(str(path))
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
        logger.debug(f"Opened file/folder: {path}")
    except Exception as e:
        log_error(
            "CLI",
            f"Could not open file/folder {path}: {e}",
            exception=e,
        )
        print(f"[red]Could not open file/folder: {e}[/red]")


def _open_html_summary(html_path: Path) -> None:
    """Open the HTML summary in the default browser."""
    if not html_path.exists():
        print(f"[yellow]HTML summary not found: {html_path}[/yellow]")
        logger.warning(f"HTML summary not found: {html_path}")
        return

    try:
        webbrowser.open(f"file://{html_path}")
        logger.debug(f"Opened HTML summary: {html_path}")
    except Exception as e:
        log_error(
            "CLI",
            f"Could not open HTML summary {html_path}: {e}",
            exception=e,
        )
        print(f"[red]Could not open HTML summary: {e}[/red]")


def _open_stats_file(txt_path: Path) -> None:
    """Open the stats file in the default application."""
    if not txt_path.exists():
        print(f"[yellow]Stats file not found: {txt_path}[/yellow]")
        logger.warning(f"Stats file not found: {txt_path}")
        return

    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(txt_path)], check=False)
        elif sys.platform == "win32":
            os.startfile(str(txt_path))
        else:
            subprocess.run(["xdg-open", str(txt_path)], check=False)
        logger.debug(f"Opened stats file: {txt_path}")
    except Exception as e:
        log_error(
            "CLI",
            f"Could not open stats.txt {txt_path}: {e}",
            exception=e,
        )
        print(f"[red]Could not open stats.txt: {e}[/red]")


def find_smallest_transcript() -> Path | None:
    """
    Find the smallest available transcript file for testing.

    Searches the default transcript folder recursively for JSON transcript files
    and returns the one with the smallest file size (or segment count if available).

    Returns:
        Path to the smallest transcript file, or None if no transcripts found
    """
    from transcriptx.core.utils.config import get_config
    from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
    import json

    config = get_config()
    default_folder = Path(config.output.default_transcript_folder)

    # If default folder doesn't exist, try DIARISED_TRANSCRIPTS_DIR
    if not default_folder.exists():
        default_folder = Path(DIARISED_TRANSCRIPTS_DIR)

    # If still doesn't exist, return None
    if not default_folder.exists():
        logger.warning(f"Transcript folder does not exist: {default_folder}")
        return None

    # Find all JSON transcript files recursively
    transcript_files = list(default_folder.rglob("*.json"))

    if not transcript_files:
        logger.warning(f"No transcript files found in {default_folder}")
        return None

    # Find the smallest transcript by file size
    # If we can read the JSON, prefer segment count as a better metric
    smallest_file = None
    smallest_size = float("inf")
    smallest_segment_count = float("inf")

    for transcript_file in transcript_files:
        try:
            file_size = transcript_file.stat().st_size

            # Try to get segment count for better comparison
            try:
                with open(transcript_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "segments" in data:
                        segment_count = len(data["segments"])
                        # Prefer segment count over file size
                        if segment_count < smallest_segment_count:
                            smallest_segment_count = segment_count
                            smallest_file = transcript_file
                            smallest_size = file_size
                            continue
            except (json.JSONDecodeError, OSError, KeyError):
                pass  # Fall back to file size

            # Use file size if segment count not available
            if file_size < smallest_size:
                smallest_size = file_size
                smallest_file = transcript_file
        except OSError:
            continue  # Skip files we can't access

    if smallest_file:
        logger.info(
            f"Found smallest transcript: {smallest_file} ({smallest_size} bytes, {smallest_segment_count if smallest_segment_count != float('inf') else 'N/A'} segments)"
        )

    return smallest_file


def run_test_analysis_workflow() -> None:
    """
    Run a test analysis on the smallest available transcript.

    This function automatically finds the smallest transcript and runs the full
    analysis pipeline on it, skipping the interactive selection process.
    This is useful for quickly testing the pipeline.
    """
    with graceful_exit():
        try:
            print("\n[bold cyan]🧪 Test Analysis[/bold cyan]")
            print("[dim]Finding smallest available transcript for testing...[/dim]")

            # Find the smallest transcript
            transcript_file = find_smallest_transcript()
            if not transcript_file:
                print(
                    "\n[red]❌ No transcript files found. Please ensure transcripts are available in the default transcript folder.[/red]"
                )
                logger.warning("No transcripts found for test analysis")
                return

            print(f"\n[green]✅ Found transcript: {transcript_file.name}[/green]")

            # Get file size and segment count for display
            try:
                file_size_kb = transcript_file.stat().st_size / 1024
                import json

                with open(transcript_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "segments" in data:
                        segment_count = len(data["segments"])
                        print(
                            f"[dim]Size: {file_size_kb:.1f} KB, Segments: {segment_count}[/dim]"
                        )
                    else:
                        print(f"[dim]Size: {file_size_kb:.1f} KB[/dim]")
            except Exception:
                pass

            # Use quick mode for testing (faster)
            print("\n[bold]Running full analysis pipeline with all modules...[/bold]")
            logger.info(
                f"Starting test analysis workflow for transcript: {transcript_file}"
            )

            # Get all available modules
            all_modules = get_default_modules()

            # Apply quick mode settings for faster testing (non-interactive)
            apply_analysis_mode_settings_non_interactive("quick")

            # Filter modules based on mode
            filtered_modules = filter_modules_by_mode(all_modules, "quick")

            print(f"[dim]Modules: {', '.join(filtered_modules)}[/dim]")

            # Run analysis with enhanced progress tracking
            try:
                from transcriptx.core.utils.config import get_config

                config = get_config()
                workflow_config = config.workflow
                skip_speaker_mapping = True

                # Use quick mode timeout
                timeout_seconds = workflow_config.timeout_quick_seconds

                # Set up progress tracking
                progress_config = ProgressConfig(
                    update_interval=workflow_config.update_interval,
                    show_percentage=True,
                    show_memory=True,
                    show_time_remaining=True,
                    show_speed=True,
                    timeout=timeout_seconds,
                    timeout_warn_only=True,
                    graceful_exit=True,
                )

                with process_spinner(
                    "Running test analysis pipeline", progress_config
                ) as tracker:
                    with resource_monitor("Test analysis pipeline"):
                        results = run_analysis_pipeline(
                            target=str(transcript_file),
                            selected_modules=filtered_modules,
                            skip_speaker_mapping=skip_speaker_mapping,
                            persist=False,
                        )

                        # Update progress to completion
                        tracker.update(100 - tracker.current)

                # Show analysis status
                try:
                    from transcriptx.core.utils.state_utils import get_analysis_history

                    analysis_status = get_analysis_history(str(transcript_file))
                    if analysis_status:
                        status = analysis_status.get("status", "unknown")
                        modules_run = analysis_status.get("modules_run", [])
                        modules_failed = analysis_status.get("modules_failed", [])

                        if status == "completed":
                            print(
                                "\n[green]✅ Test analysis completed successfully![/green]"
                            )
                            print(f"[dim]Modules run: {', '.join(modules_run)}[/dim]")
                        elif status == "partial":
                            print(
                                f"\n[yellow]⚠️ Test analysis completed partially ({len(modules_run)}/{len(analysis_status.get('modules_requested', []))} modules)[/yellow]"
                            )
                            if modules_failed:
                                print(
                                    f"[dim]Failed modules: {', '.join(modules_failed)}[/dim]"
                                )
                        elif status == "failed":
                            print(f"\n[red]❌ Test analysis failed[/red]")
                        else:
                            print(
                                f"\n[yellow]⚠️ Test analysis status: {status}[/yellow]"
                            )

                        if results.get("errors"):
                            print(f"[yellow]Errors: {len(results['errors'])}[/yellow]")
                            for error in results["errors"]:
                                print(f"  • {error}")
                except Exception as e:
                    logger.debug(f"Could not get analysis status from state: {e}")
                    if results.get("errors"):
                        print(
                            f"\n[yellow]⚠️ Test analysis completed with {len(results['errors'])} errors.[/yellow]"
                        )
                        for error in results["errors"]:
                            print(f"  • {error}")
                    else:
                        print(
                            "\n[green]✅ Test analysis completed successfully![/green]"
                        )

                output_dir = results.get("output_dir") or get_transcript_dir(
                    str(transcript_file)
                )
                print(f"Output directory: {output_dir}")
                logger.info(f"Test analysis completed for {transcript_file}")

                # Note: Comprehensive summary is already generated by StatsAnalysis module during pipeline execution
                # No need to call deprecated generate_stats_from_file() - stats module handles this internally

                print("\n[green]✅ Test analysis complete![/green]")

            except Exception as e:
                log_error(
                    "CLI",
                    f"Test analysis workflow failed for {transcript_file}: {e}",
                    exception=e,
                )
                print(f"\n[red]❌ Test analysis failed: {e}[/red]")

        except KeyboardInterrupt:
            print("\n[cyan]Test analysis cancelled. Returning to main menu.[/cyan]")


def run_analysis_non_interactive(
    transcript_file: Path | str,
    mode: str = "quick",
    modules: list[str] | None = None,
    profile: str | None = None,
    skip_confirm: bool = False,
    output_dir: Path | str | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    """
    Run analysis workflow non-interactively with provided parameters.

    Args:
        transcript_file: Path to transcript JSON file
        mode: Analysis mode - 'quick' or 'full' (default: 'quick')
        modules: List of module names or None for all modules (default: None/all)
        profile: Semantic profile for full mode - 'balanced', 'academic', 'business',
                'casual', 'technical', 'interview' (only used with mode='full')
        skip_confirm: Skip confirmation prompts (default: False)
        output_dir: Custom output directory (optional)

    Returns:
        Dictionary containing analysis results and metadata

    Raises:
        FileNotFoundError: If transcript file doesn't exist
        ValueError: If invalid parameters provided
    """
    from transcriptx.core.utils.config import get_config

    # Convert to Path if string
    if isinstance(transcript_file, str):
        transcript_file = Path(transcript_file)

    # Validate transcript file exists
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript file not found: {transcript_file}")

    # Validate mode
    if mode not in ["quick", "full"]:
        raise ValueError(f"Invalid analysis mode: {mode}. Must be 'quick' or 'full'")

    # Validate profile if provided
    if profile and profile not in [
        "balanced",
        "academic",
        "business",
        "casual",
        "technical",
        "interview",
    ]:
        raise ValueError(
            f"Invalid profile: {profile}. Must be one of: balanced, academic, business, casual, technical, interview"
        )

    # Get available modules
    available_modules = get_available_modules()
    default_modules = get_default_modules()

    # Determine modules to use
    if modules is None:
        selected_modules = default_modules
    elif isinstance(modules, str) and modules.lower() == "all":
        selected_modules = default_modules
    else:
        # Validate module names
        invalid_modules = [m for m in modules if m not in available_modules]
        if invalid_modules:
            raise ValueError(
                f"Invalid module names: {', '.join(invalid_modules)}. Available modules: {', '.join(available_modules)}"
            )
        selected_modules = modules

    # Apply analysis mode settings
    apply_analysis_mode_settings_non_interactive(mode, profile)

    # Filter modules based on analysis mode
    filtered_modules = filter_modules_by_mode(selected_modules, mode)

    # In non-interactive mode we must not block on speaker mapping prompts.
    # Speaker IDs (e.g. SPEAKER_00) will be treated as "unnamed" and excluded by
    # many modules unless the transcript already contains named speakers.
    skip_speaker_mapping = True

    # Update output directory if specified
    if output_dir:
        config = get_config()
        if isinstance(output_dir, str):
            output_dir = Path(output_dir)
        config.output.base_output_dir = str(output_dir)
        logger.info(f"Updated output directory to: {output_dir}")

    # Show what will be analyzed
    print(f"\n[bold]Analyzing transcript:[/bold] {transcript_file.name}")
    print(f"[dim]Mode: {mode}[/dim]")
    if mode == "full" and profile:
        print(f"[dim]Profile: {profile}[/dim]")
    print(f"[dim]Modules: {', '.join(filtered_modules)}[/dim]")
    logger.info(
        f"Starting non-interactive analysis workflow for transcript: {transcript_file}"
    )

    # Confirm if not skipped
    if not skip_confirm:
        print(f"\n[bold]Selected modules:[/bold] {', '.join(filtered_modules)}")
        from rich.prompt import Confirm

        if not Confirm.ask("Proceed with analysis?"):
            return {"status": "cancelled", "errors": []}

    # Run analysis with enhanced progress tracking
    try:
        # Get analysis mode to determine timeout
        config = get_config()
        analysis_mode = config.analysis.analysis_mode
        workflow_config = config.workflow

        # Set timeout based on analysis mode: use config values
        if analysis_mode == "full":
            timeout_seconds = workflow_config.timeout_full_seconds
        else:
            timeout_seconds = workflow_config.timeout_quick_seconds

        # Set up progress tracking
        progress_config = ProgressConfig(
            update_interval=workflow_config.update_interval,
            show_percentage=True,
            show_memory=True,
            show_time_remaining=True,
            show_speed=True,
            timeout=timeout_seconds,
            timeout_warn_only=True,  # Log warning instead of crashing pipeline
            graceful_exit=True,
        )

        with process_spinner("Running analysis pipeline", progress_config) as tracker:
            with resource_monitor("Analysis pipeline"):
                results = run_analysis_pipeline(
                    target=str(transcript_file),
                    selected_modules=filtered_modules,
                    skip_speaker_mapping=skip_speaker_mapping,
                    persist=persist,
                )

                # Update progress to completion
                tracker.update(100 - tracker.current)

        # Show analysis status from state
        try:
            from transcriptx.core.utils.state_utils import get_analysis_history

            analysis_status = get_analysis_history(str(transcript_file))
            if analysis_status:
                status = analysis_status.get("status", "unknown")
                modules_run = analysis_status.get("modules_run", [])
                modules_failed = analysis_status.get("modules_failed", [])

                if status == "completed":
                    print("\n[green]✅ Analysis completed successfully![/green]")
                    print(f"[dim]Modules run: {', '.join(modules_run)}[/dim]")
                elif status == "partial":
                    print(
                        f"\n[yellow]⚠️ Analysis completed partially ({len(modules_run)}/{len(analysis_status.get('modules_requested', []))} modules)[/yellow]"
                    )
                    if modules_failed:
                        print(f"[dim]Failed modules: {', '.join(modules_failed)}[/dim]")
                elif status == "failed":
                    print(f"\n[red]❌ Analysis failed[/red]")
                else:
                    print(f"\n[yellow]⚠️ Analysis status: {status}[/yellow]")

                if results.get("errors"):
                    print(f"[yellow]Errors: {len(results['errors'])}[/yellow]")
                    for error in results["errors"]:
                        print(f"  • {error}")
        except Exception as e:
            # Fallback to original behavior if state lookup fails
            logger.debug(f"Could not get analysis status from state: {e}")
            if results.get("errors"):
                print(
                    f"\n[yellow]⚠️ Analysis completed with {len(results['errors'])} errors.[/yellow]"
                )
                for error in results["errors"]:
                    print(f"  • {error}")
            else:
                print("\n[green]✅ Analysis completed successfully![/green]")

        output_dir_path = get_transcript_dir(str(transcript_file))
        print(f"Output directory: {output_dir_path}")
        logger.info(f"Analysis completed for {transcript_file}")

        # Note: Comprehensive summary is already generated by StatsAnalysis module during pipeline execution
        # No need to call deprecated generate_stats_from_file() - stats module handles this internally

        # Return results
        return {
            "status": "completed",
            "transcript_file": str(transcript_file),
            "output_dir": str(output_dir_path),
            "modules_run": results.get("modules_run", []),
            "errors": results.get("errors", []),
        }

    except Exception as e:
        log_error(
            "CLI",
            f"Analysis workflow failed for {transcript_file}: {e}",
            exception=e,
        )
        print(f"\n[red]❌ Analysis failed: {e}[/red]")
        return {
            "status": "failed",
            "transcript_file": str(transcript_file),
            "error": str(e),
            "errors": [str(e)],
        }
