"""
Batch workflow functions for post-processing operations.

This module provides batch processing workflows for speaker identification
and analysis pipeline operations on multiple transcripts.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

import questionary
from rich import print

from transcriptx.cli.analysis_utils import (
    apply_analysis_mode_settings,
    apply_analysis_mode_settings_non_interactive,
    select_analysis_mode,
)
from transcriptx.core.utils.config import get_config
from transcriptx.cli.file_processor import _offer_tag_editing
from transcriptx.cli.processing_state import (
    get_current_transcript_path_from_state,
    load_processing_state,
    save_processing_state,
)
from transcriptx.core import run_analysis_pipeline
from transcriptx.core.pipeline.target_resolver import TranscriptRef
from transcriptx.core.utils.file_rename import rename_transcript_after_speaker_mapping
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.path_utils import resolve_file_path
from transcriptx.database.services.transcript_store_policy import (
    store_transcript_after_speaker_identification,
)
from transcriptx.io.speaker_mapping import build_speaker_map
from transcriptx.io.transcript_loader import (
    load_segments,
    extract_speaker_map_from_transcript,
)
from transcriptx.cli.speaker_utils import (
    SpeakerGateDecision,
    check_batch_speaker_gate,
    check_speaker_identification_status,
)

logger = get_logger()


def _resolve_transcript_path(transcript_path: str) -> str:
    """
    Resolve a transcript path to an existing file.

    This function uses the unified path resolution system.

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


def _ensure_transcript_uuid(transcript_path: str) -> str:
    """
    Get or create UUID for transcript.

    This is a wrapper that imports from processing_state to avoid circular imports.

    Args:
        transcript_path: Path to transcript file

    Returns:
        UUID string for the transcript file
    """
    # Import the function directly - it's used internally but we need it here
    import importlib

    processing_state = importlib.import_module("transcriptx.cli.processing_state")
    return processing_state._ensure_transcript_uuid(transcript_path)


def run_batch_speaker_identification(
    transcript_paths: List[str],
    from_gate: bool = False,
) -> None:
    """
    Run speaker identification sequentially for all transcripts from batch processing.

    This function processes each transcript one by one, allowing the user to
    identify speakers for each transcript. It provides progress tracking and
    allows users to skip individual transcripts or cancel the entire batch.

    When from_gate is True (invoked from a "speaker ID needed" step), only
    unidentified speakers are shown per transcript; already-named speakers are skipped.

    Args:
        transcript_paths: List of transcript file paths to process
        from_gate: If True, only show unidentified speakers (used when entering from gate).
    """
    if not transcript_paths:
        print(
            "\n[yellow]⚠️ No transcripts to process for speaker identification.[/yellow]"
        )
        return

    # Filter out transcripts that already have speaker maps (optional)
    # First resolve all paths to handle renamed files
    resolved_transcript_paths = []
    for transcript_path in transcript_paths:
        try:
            rerun_mode = "reuse-existing-run"
            resolved_path = _resolve_transcript_path(transcript_path)
            resolved_transcript_paths.append(resolved_path)
        except FileNotFoundError:
            logger.warning(
                f"Could not resolve transcript path: {transcript_path}, skipping"
            )
            continue

    transcripts_to_process = []
    # All transcripts need processing (speaker identification is database-driven)
    transcripts_to_process = resolved_transcript_paths

    print("\n[bold cyan]🗣️ Batch Speaker Identification[/bold cyan]")
    print(f"[dim]Processing {len(transcripts_to_process)} transcript(s)...[/dim]")

    successful = []
    skipped = []
    failed = []

    for idx, transcript_path in enumerate(transcripts_to_process, 1):
        transcript_name = Path(transcript_path).name
        print(
            f"\n[bold]Processing transcript {idx} of {len(transcripts_to_process)}:[/bold] {transcript_name}"
        )

        # Resolve transcript path once at the start
        resolved_path = transcript_path
        try:
            resolved_path = _resolve_transcript_path(transcript_path)
            if resolved_path != transcript_path:
                logger.debug(
                    f"Resolved transcript path: {transcript_path} -> {resolved_path}"
                )
        except FileNotFoundError as e:
            logger.error(
                f"Could not resolve transcript path for {transcript_name}: {e}"
            )
            failed.append(transcript_path)
            print(f"[red]❌ Could not find transcript file: {transcript_name}[/red]")
            continue

        # Check if user wants to skip this transcript
        if questionary.confirm(
            f"Process speaker identification for {transcript_name}?", default=True
        ).ask():
            try:
                # Load segments
                segments = load_segments(resolved_path)

                # Run speaker identification (database-driven, no JSON files)
                print(
                    f"[cyan]Running speaker identification for {transcript_name}...[/cyan]"
                )
                existing_map = (
                    extract_speaker_map_from_transcript(resolved_path)
                    if from_gate
                    else None
                )
                speaker_map = build_speaker_map(
                    segments,
                    speaker_map_path=None,  # No JSON file path needed
                    review_mode="unidentified only" if from_gate else "all",
                    existing_map=existing_map,
                    transcript_path=resolved_path,
                    batch_mode=False,  # Use interactive mode for batch processing
                    auto_generate=False,
                    persist_speaker_records=False,
                )

                if speaker_map:
                    print(
                        f"[green]✅ Speaker identification completed for {transcript_name}![/green]"
                    )
                    # Prompt for rename after speaker mapping is completed
                    rename_transcript_after_speaker_mapping(resolved_path)

                    # Get updated path after renaming (from processing state)
                    updated_path = (
                        get_current_transcript_path_from_state(resolved_path)
                        or resolved_path
                    )
                    if updated_path != resolved_path:
                        logger.debug(
                            f"Path updated after rename: {resolved_path} -> {updated_path}"
                        )
                        resolved_path = updated_path

                    if Path(resolved_path).exists():
                        store_transcript_after_speaker_identification(resolved_path)
                    else:
                        logger.warning(
                            f"Transcript path not found after rename: {resolved_path}"
                        )

                    # Offer tag editing after renaming (use updated path)
                    _offer_tag_editing(resolved_path)

                    successful.append(resolved_path)
                else:
                    print(
                        f"[yellow]⏭️ Speaker identification cancelled for {transcript_name}[/yellow]"
                    )
                    skipped.append(resolved_path)

            except KeyboardInterrupt:
                print(
                    f"\n[yellow]⚠️ Speaker identification cancelled for {transcript_name}[/yellow]"
                )
                if questionary.confirm(
                    "Cancel entire batch speaker identification?"
                ).ask():
                    print("\n[cyan]Batch speaker identification cancelled.[/cyan]")
                    return
                skipped.append(resolved_path)
            except Exception as e:
                log_error(
                    "BATCH_SPEAKER_ID",
                    f"Speaker identification failed for {resolved_path}: {e}",
                    exception=e,
                )
                print(
                    f"[red]❌ Speaker identification failed for {transcript_name}: {e}[/red]"
                )
                failed.append(resolved_path)
        else:
            print(f"[yellow]⏭️ Skipped {transcript_name}[/yellow]")
            skipped.append(transcript_path)

    # Show summary
    print("\n" + "=" * 60)
    print("[bold green]📊 Batch Speaker Identification Summary[/bold green]")
    print("=" * 60)
    print(f"\n[bold]Total transcripts:[/bold] {len(transcripts_to_process)}")
    print(f"[green]✅ Successful:[/green] {len(successful)}")
    print(f"[yellow]⏭️ Skipped:[/yellow] {len(skipped)}")
    print(f"[red]❌ Failed:[/red] {len(failed)}")
    print("=" * 60)

    # When from_gate=True, the caller (e.g. group or batch analysis) will continue with the
    # full set of transcripts; do not offer analysis on only this subset.
    if from_gate:
        return

    # Offer batch analysis pipeline on all transcripts that are ready (successful + skipped)
    ready_for_analysis = successful + skipped
    if ready_for_analysis:
        print("\n[bold cyan]🔍 Analysis Pipeline[/bold cyan]")
        if questionary.confirm(
            f"Would you like to run the analysis pipeline on {len(ready_for_analysis)} transcript(s)?"
        ).ask():
            run_batch_analysis_pipeline(ready_for_analysis)


def run_batch_analysis_pipeline(
    transcript_paths: List[str],
    analysis_mode: str | None = None,
    selected_modules: List[str] | None = None,
    skip_speaker_gate: bool = False,
    speaker_options: "SpeakerRunOptions | None" = None,
    persist: bool = False,
) -> None:
    """
    Run analysis pipeline sequentially for all transcripts from batch processing.

    This function processes each transcript one by one, running the full analysis
    pipeline on each. It provides progress tracking and allows users to skip
    individual transcripts or cancel the entire batch.

    Args:
        transcript_paths: List of transcript file paths to process
        analysis_mode: Optional pre-selected analysis mode ('quick' or 'full').
                      If None, user will be prompted to select.
        selected_modules: Optional pre-selected analysis modules.
                         If None, user will be prompted to select.
        skip_speaker_gate: Skip speaker identification gate if already handled upstream.
        speaker_options: Run-level speaker options for anonymisation and inclusion.
        persist: Persist run metadata and artifacts to DB.
    """
    if not transcript_paths:
        print("\n[yellow]⚠️ No transcripts to process for analysis.[/yellow]")
        return

    print("\n[bold cyan]🔍 Batch Analysis Pipeline[/bold cyan]")
    print(f"[dim]Processing {len(transcript_paths)} transcript(s)...[/dim]")

    # Select analysis mode once for all transcripts (if not provided)
    if analysis_mode is None:
        print("\n[bold]Select analysis mode for batch processing:[/bold]")
        analysis_mode = select_analysis_mode()
        apply_analysis_mode_settings(analysis_mode)
    else:
        # Mode already selected - use non-interactive version to preserve existing profile
        config = get_config()
        current_profile = config.analysis.quality_filtering_profile
        apply_analysis_mode_settings_non_interactive(analysis_mode, current_profile)

    # Get all available modules (or allow selection) if not provided
    if selected_modules is None:
        from transcriptx.cli.analysis_utils import select_analysis_modules

        print("\n[bold]Select analysis modules:[/bold]")
        selected_modules, _ = select_analysis_modules(transcript_paths)
        if not selected_modules:
            print("\n[cyan]Analysis cancelled. Returning to main menu.[/cyan]")
            return

    # Resolve all paths upfront to handle renamed files and filter out invalid paths
    resolved_transcript_paths = []
    invalid_paths = []
    for transcript_path in transcript_paths:
        try:
            resolved_path = _resolve_transcript_path(transcript_path)
            resolved_transcript_paths.append(resolved_path)
            if resolved_path != transcript_path:
                logger.debug(
                    f"Resolved transcript path: {transcript_path} -> {resolved_path}"
                )
        except FileNotFoundError:
            logger.warning(
                f"Could not resolve transcript path: {transcript_path}. File may have been renamed. Skipping."
            )
            invalid_paths.append(transcript_path)

    if invalid_paths:
        print(
            f"\n[yellow]⚠️ Warning: {len(invalid_paths)} transcript(s) could not be found and will be skipped:[/yellow]"
        )
        for path in invalid_paths:
            print(f"  - {Path(path).name}")

    if not resolved_transcript_paths:
        print("\n[yellow]⚠️ No valid transcripts to process for analysis.[/yellow]")
        return

    from transcriptx.core.pipeline.run_options import SpeakerRunOptions

    speaker_options = speaker_options or SpeakerRunOptions()
    decision = SpeakerGateDecision.PROCEED
    needs_identification: List[str] = []
    already_identified: List[str] = []
    statuses: dict[str, Any] = {}
    identified_paths: set[str] = set()
    if not skip_speaker_gate:
        decision, needs_identification, already_identified, statuses = (
            check_batch_speaker_gate(resolved_transcript_paths)
        )
        if decision == SpeakerGateDecision.SKIP:
            return
        if decision == SpeakerGateDecision.IDENTIFY and needs_identification:
            run_batch_speaker_identification(needs_identification, from_gate=True)
            updated_paths: List[str] = []
            for path in resolved_transcript_paths:
                if path in needs_identification:
                    updated_path = get_current_transcript_path_from_state(path) or path
                    identified_paths.add(updated_path)
                    statuses[updated_path] = check_speaker_identification_status(
                        updated_path
                    )
                    updated_paths.append(updated_path)
                else:
                    updated_paths.append(path)
            resolved_transcript_paths = updated_paths
            # Recompute status lists based on updated data
            needs_identification = []
            already_identified = []
            for path in resolved_transcript_paths:
                status = statuses.get(path) or check_speaker_identification_status(path)
                statuses[path] = status
                if status.is_complete or status.total_count == 0:
                    already_identified.append(path)
                else:
                    needs_identification.append(path)

    skip_speaker_mapping_by_path: dict[str, bool] = {}
    if decision == SpeakerGateDecision.IDENTIFY:
        for path in resolved_transcript_paths:
            skip_speaker_mapping_by_path[path] = path not in identified_paths
    else:
        for path in resolved_transcript_paths:
            skip_speaker_mapping_by_path[path] = True

    # Check all transcripts upfront to see which ones are already completed
    # This prevents interruption during batch processing
    from transcriptx.core.utils.state_utils import has_analysis_completed

    transcripts_needing_analysis: List[str] = []
    transcripts_already_completed: List[str] = []
    rerun_modes: dict[str, str] = {}  # Map transcript_path -> rerun_mode

    print(
        f"\n[cyan]Checking analysis status for {len(resolved_transcript_paths)} transcript(s)...[/cyan]"
    )

    for transcript_path in resolved_transcript_paths:
        try:
            # Ensure state entry exists before checking
            try:
                state = load_processing_state()
                processed_files = state.get("processed_files", {})

                # Check if entry exists for this transcript
                entry_exists = False
                for file_key, entry in processed_files.items():
                    if entry.get("transcript_path") == transcript_path:
                        entry_exists = True
                        break

                # If no entry exists, create a minimal one
                if not entry_exists:
                    # Try to find entry by base name or create new one
                    from transcriptx.core.utils.path_utils import (
                        get_canonical_base_name,
                    )

                    canonical_base = get_canonical_base_name(transcript_path)

                    # Look for any entry with matching base name
                    found_key = None
                    for file_key, entry in processed_files.items():
                        entry_base = entry.get("canonical_base_name")
                        if entry_base == canonical_base:
                            # Update transcript_path to current path
                            entry["transcript_path"] = transcript_path
                            entry["last_updated"] = datetime.now().isoformat()
                            found_key = file_key
                            break

                    if not found_key:
                        # Create minimal entry with UUID
                        transcript_uuid = _ensure_transcript_uuid(transcript_path)
                        new_entry = {
                            "transcript_uuid": transcript_uuid,
                            "processed_at": datetime.now().isoformat(),
                            "status": "completed",
                            "transcript_path": transcript_path,
                            "mp3_path": None,  # May not be available
                            "analysis_completed": False,
                            "last_updated": datetime.now().isoformat(),
                        }
                        from transcriptx.core.utils.state_schema import (
                            enrich_state_entry,
                        )

                        new_entry = enrich_state_entry(new_entry, transcript_path)
                        # Use UUID as key
                        processed_files[transcript_uuid] = new_entry

                    state["processed_files"] = processed_files
                    save_processing_state(state)
                    logger.debug(f"Created/updated state entry for {transcript_path}")
            except Exception as e:
                # Don't fail analysis if state update fails
                logger.warning(f"Could not ensure state entry exists: {e}")

            # Check if analysis already completed
            already_completed = has_analysis_completed(
                transcript_path, selected_modules
            )

            if already_completed:
                transcripts_already_completed.append(transcript_path)
                rerun_modes[transcript_path] = (
                    "reuse-existing-run"  # Default, may be changed
                )
            else:
                transcripts_needing_analysis.append(transcript_path)
                rerun_modes[transcript_path] = "reuse-existing-run"
        except Exception as e:
            # If check fails, assume it needs analysis
            logger.debug(
                f"Could not check analysis completion status for {transcript_path}: {e}"
            )
            transcripts_needing_analysis.append(transcript_path)
            rerun_modes[transcript_path] = "reuse-existing-run"

    # Handle already-completed transcripts upfront
    skip_choice: Optional[str] = None
    if transcripts_already_completed:
        print(
            f"\n[yellow]⚠️ Found {len(transcripts_already_completed)} transcript(s) with completed analysis:[/yellow]"
        )
        for path in transcripts_already_completed:
            print(f"  - {Path(path).name}")

        skip_choice = questionary.select(
            f"What would you like to do with these {len(transcripts_already_completed)} already-analyzed transcript(s)?",
            choices=[
                "⏭️ Skip all already-analyzed transcripts",
                "🔄 Re-run analysis for all already-analyzed transcripts",
            ],
            default="⏭️ Skip all already-analyzed transcripts",
        ).ask()

        if skip_choice == "🔄 Re-run analysis for all already-analyzed transcripts":
            # Add them back to the processing list with rerun mode
            transcripts_needing_analysis.extend(transcripts_already_completed)
            for path in transcripts_already_completed:
                rerun_modes[path] = "new-run"
        else:
            # Keep them in the skipped list
            pass  # They'll be added to skipped list later

    # Update resolved paths to only include those that need processing
    if transcripts_needing_analysis:
        print(
            f"\n[green]✅ Will run {len(selected_modules)} module(s) on {len(transcripts_needing_analysis)} transcript(s)[/green]"
        )
        if not questionary.confirm("Proceed with batch analysis?").ask():
            print("\n[cyan]Batch analysis cancelled.[/cyan]")
            return
    else:
        print(
            "\n[yellow]⚠️ No transcripts need analysis (all are already completed or skipped).[/yellow]"
        )
        return

    successful = []
    skipped = []
    failed = []

    # Add already-completed transcripts that were skipped to the skipped list
    if (
        transcripts_already_completed
        and skip_choice
        and skip_choice == "⏭️ Skip all already-analyzed transcripts"
    ):
        for path in transcripts_already_completed:
            skipped.append(path)

    for idx, transcript_path in enumerate(transcripts_needing_analysis, 1):
        transcript_name = Path(transcript_path).name
        print(
            f"\n[bold]Processing transcript {idx} of {len(transcripts_needing_analysis)}:[/bold] {transcript_name}"
        )

        try:
            # Path is already resolved upfront, so we can use it directly
            resolved_path = transcript_path
            rerun_mode = rerun_modes.get(resolved_path, "reuse-existing-run")

            print(f"[cyan]Running analysis pipeline for {transcript_name}...[/cyan]")

            # Run analysis pipeline with skip_speaker_mapping since speakers are already identified
            # State will be updated automatically by the pipeline
            skip_speaker_mapping = skip_speaker_mapping_by_path.get(resolved_path, True)
            run_analysis_pipeline(
                target=TranscriptRef(path=resolved_path),
                selected_modules=selected_modules,
                skip_speaker_mapping=skip_speaker_mapping,
                speaker_options=speaker_options,
                persist=persist,
                rerun_mode=rerun_mode,
            )

            print(f"[green]✅ Analysis completed for {transcript_name}![/green]")
            # Use resolved path in success list (current path after any renaming)
            successful.append(resolved_path)

        except KeyboardInterrupt:
            print(f"\n[yellow]⚠️ Analysis cancelled for {transcript_name}[/yellow]")
            if questionary.confirm("Cancel entire batch analysis?").ask():
                print("\n[cyan]Batch analysis cancelled.[/cyan]")
                return
            # Try to resolve path for skipped list
            try:
                resolved_path = _resolve_transcript_path(transcript_path)
                skipped.append(resolved_path)
            except FileNotFoundError:
                skipped.append(transcript_path)
        except Exception as e:
            log_error(
                "BATCH_ANALYSIS",
                f"Analysis pipeline failed for {transcript_path}: {e}",
                exception=e,
            )
            print(f"[red]❌ Analysis failed for {transcript_name}: {e}[/red]")
            # Try to resolve path for failed list
            try:
                resolved_path = _resolve_transcript_path(transcript_path)
                failed.append(resolved_path)
            except FileNotFoundError:
                failed.append(transcript_path)

    # Show summary
    print("\n" + "=" * 60)
    print("[bold green]📊 Batch Analysis Pipeline Summary[/bold green]")
    print("=" * 60)
    print(f"\n[bold]Total transcripts:[/bold] {len(resolved_transcript_paths)}")
    print(f"[green]✅ Successful:[/green] {len(successful)}")
    print(f"[yellow]⏭️ Skipped:[/yellow] {len(skipped)}")
    print(f"[red]❌ Failed:[/red] {len(failed)}")
    print("=" * 60)
