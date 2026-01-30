"""
Speaker Identification Workflow Module for TranscriptX CLI.

This module contains the speaker identification workflow that was previously
embedded in the main CLI. It provides a clean, reusable interface for
running speaker identification with proper error handling and user feedback.

Key Features:
- Interactive transcript file selection
- Speaker map validation and creation
- Interactive speaker identification process
- Integration with centralized path utilities
"""

from pathlib import Path
from typing import Any

from rich import print

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.file_rename import rename_transcript_after_speaker_mapping
from transcriptx.utils.error_handling import graceful_exit
from transcriptx.io import load_segments
from transcriptx.io.speaker_mapping import build_speaker_map
from transcriptx.database.services.transcript_store_policy import (
    store_transcript_after_speaker_identification,
)
from transcriptx.cli.processing_state import get_current_transcript_path_from_state

# Import CLI utilities
from .file_selection_utils import select_folder_interactive
from .file_selection_interface import FileSelectionConfig, select_files_interactive
from .speaker_utils import has_named_speakers

logger = get_logger()


def run_speaker_identification_workflow() -> None:
    """
    Run the complete speaker identification workflow.

    This function orchestrates the entire speaker identification process:
    1. Transcript file selection
    2. Speaker map validation
    3. Interactive speaker identification
    4. Speaker map creation/update

    Returns:
        None: Speaker map is saved to disk
    """
    with graceful_exit():
        _run_speaker_identification_workflow_impl()


def _run_speaker_identification_workflow_impl() -> None:
    """Internal implementation of the speaker identification workflow."""
    try:
        # Implement speaker identification logic
        print("\n[bold cyan]🗣️ Identify Speakers[/bold cyan]")

        # Select folder
        config = get_config()
        default_folder = Path(config.output.default_transcript_folder)
        if not default_folder.exists():
            # Create the directory if it doesn't exist
            default_folder.mkdir(parents=True, exist_ok=True)
        folder_path = select_folder_interactive(start_path=default_folder)
        if not folder_path:
            return

        transcript_files = list(folder_path.glob("*.json"))
        transcript_files = sorted(transcript_files, key=lambda p: p.name.lower())
        if not transcript_files:
            print(f"[red]❌ No transcript files (.json) found in {folder_path}[/red]")
            return

        def _format_transcript_for_speaker_id(path: Path) -> str:
            """Format transcript label: ✨ prefix if speakers not yet named."""
            name = path.name
            return f"✨ {name}" if not has_named_speakers(path) else name

        selection_config = FileSelectionConfig(
            multi_select=False,
            enable_playback=False,
            enable_rename=False,
            title="🗣️ Identify Speakers",
            current_path=folder_path,
            metadata_formatter=_format_transcript_for_speaker_id,
        )
        selected = select_files_interactive(transcript_files, selection_config)
        if not selected or len(selected) == 0:
            return

        transcript_file = selected[0]

        # Run the speaker identification pipeline
        print(f"[cyan]Running speaker identification for {transcript_file.name}...[/cyan]")
        try:
            segments = load_segments(str(transcript_file))
            # Use build_speaker_map for database-driven speaker identification
            speaker_map = build_speaker_map(
                segments,
                speaker_map_path=None,  # No JSON file path needed
                transcript_path=str(transcript_file),
                batch_mode=False,
                auto_generate=False,
                persist_speaker_records=False,
            )
            if speaker_map:
                print(
                    f"[green]✅ Speaker identification completed for {transcript_file.name}![/green]"
                )
                # Prompt for rename after speaker mapping is completed
                rename_transcript_after_speaker_mapping(str(transcript_file))
                final_path = (
                    get_current_transcript_path_from_state(str(transcript_file))
                    or str(transcript_file)
                )
                if Path(final_path).exists():
                    store_transcript_after_speaker_identification(final_path)
                else:
                    logger.warning(
                        f"Transcript path not found after rename: {final_path}"
                    )
            else:
                print(
                    f"[yellow]⏭️ Speaker identification cancelled for {transcript_file.name}[/yellow]"
                )
        except Exception as e:
            print(f"[red]❌ Speaker identification failed: {e}[/red]")

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")


def run_speaker_identification_non_interactive(
    transcript_file: Path | str,
    overwrite: bool = False,
    skip_rename: bool = False,
) -> dict[str, Any]:
    """
    Run speaker identification workflow non-interactively with provided parameters.

    Args:
        transcript_file: Path to transcript JSON file
        overwrite: Overwrite existing speaker identification without confirmation (default: False)
        skip_rename: Skip transcript rename after speaker identification (default: False)

    Returns:
        Dictionary containing speaker identification results

    Raises:
        FileNotFoundError: If transcript file doesn't exist
        ValueError: If invalid parameters provided
    """
    # Convert to Path if string
    if isinstance(transcript_file, str):
        transcript_file = Path(transcript_file)

    # Validate transcript file exists
    if not transcript_file.exists():
        raise FileNotFoundError(f"Transcript file not found: {transcript_file}")

    print(f"\n[bold cyan]🗣️ Identify Speakers[/bold cyan]")
    print(f"[bold]Transcript:[/bold] {transcript_file.name}")
    logger.info(
        f"Starting non-interactive speaker identification for: {transcript_file}"
    )

    # Run the speaker identification pipeline
    # Note: Speaker identification now works directly with database, no JSON files
    print(f"[cyan]Running speaker identification for {transcript_file.name}...[/cyan]")
    try:
        segments = load_segments(str(transcript_file))
        # Use build_speaker_map for database-driven speaker identification
        # This creates speakers in the database and updates segments with speaker_db_id
        from transcriptx.io.speaker_mapping import build_speaker_map

        speaker_map_result = build_speaker_map(
            segments,
            speaker_map_path=None,  # No JSON file path needed
            transcript_path=str(transcript_file),
            batch_mode=True,
            auto_generate=False,
            persist_speaker_records=False,
        )

        if speaker_map_result:
            print(
                f"[green]✅ Speaker identification completed for {transcript_file.name}![/green]"
            )

            # Rename transcript if not skipped
            if not skip_rename:
                rename_transcript_after_speaker_mapping(str(transcript_file))

            final_path = (
                get_current_transcript_path_from_state(str(transcript_file))
                or str(transcript_file)
            )
            if Path(final_path).exists():
                store_transcript_after_speaker_identification(final_path)
            else:
                logger.warning(f"Transcript path not found after rename: {final_path}")

            return {
                "status": "completed",
                "transcript_file": str(transcript_file),
                "speakers_identified": len(speaker_map_result),
            }
        else:
            print(
                f"[yellow]⏭️ Speaker identification cancelled for {transcript_file.name}[/yellow]"
            )
            return {
                "status": "cancelled",
                "transcript_file": str(transcript_file),
            }
    except Exception as e:
        log_error(
            "CLI",
            f"Speaker identification failed for {transcript_file}: {e}",
            exception=e,
        )
        print(f"[red]❌ Speaker identification failed: {e}[/red]")
        return {
            "status": "failed",
            "transcript_file": str(transcript_file),
            "error": str(e),
        }
