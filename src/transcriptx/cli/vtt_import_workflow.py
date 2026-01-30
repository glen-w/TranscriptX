"""
VTT import workflow for TranscriptX.

This module provides an explicit workflow for importing VTT files,
with optional coalescing configuration and summary display.
"""

from pathlib import Path
from rich import print
from rich.console import Console

from transcriptx.cli.file_selection_utils import select_folder_interactive
from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
from transcriptx.io.segment_coalescer import CoalesceConfig
from transcriptx.io.transcript_importer import import_transcript
from transcriptx.utils.error_handling import graceful_exit

console = Console()


def run_vtt_import_workflow() -> None:
    """
    Workflow for explicitly importing VTT files.

    Steps:
    1. Select VTT file
    2. Optionally configure coalescing
    3. Call import_transcript()
    4. Show summary (segments, duration, speakers)
    5. Optionally proceed to analysis
    """
    with graceful_exit():
        _run_vtt_import_workflow_impl()


def _run_vtt_import_workflow_impl() -> None:
    """Internal implementation of VTT import workflow."""
    try:
        print("\n[bold cyan]📄 Import VTT File[/bold cyan]")

        # Select folder
        config = get_config()
        default_folder = Path(config.output.default_transcript_folder)
        if not default_folder.exists():
            default_folder.mkdir(parents=True, exist_ok=True)

        folder_path = select_folder_interactive(start_path=default_folder)
        if not folder_path:
            print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
            return

        # Find VTT files
        vtt_files = list(folder_path.glob("*.vtt"))
        vtt_files = sorted(vtt_files, key=lambda p: p.name.lower())

        if not vtt_files:
            print(f"\n[red]❌ No VTT files found in {folder_path}[/red]")
            return

        # Select VTT file
        if len(vtt_files) == 1:
            selected_vtt = vtt_files[0]
            print(f"\n[dim]Selected: {selected_vtt.name}[/dim]")
        else:
            import questionary

            choices = [f.name for f in vtt_files]
            selected_name = questionary.select(
                "Select VTT file to import:",
                choices=choices,
            ).ask()

            if not selected_name:
                print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
                return

            selected_vtt = folder_path / selected_name

        # Ask about coalescing
        import questionary

        coalesce_enabled = questionary.confirm(
            "Enable segment coalescing? (merge adjacent subtitles)",
            default=False,
        ).ask()

        coalesce_config = None
        if coalesce_enabled:
            # Get coalescing settings from config if available
            config_obj = get_config()
            vtt_config = getattr(config_obj, "vtt_import", None)

            if vtt_config:
                coalesce_config = CoalesceConfig(
                    enabled=True,
                    max_gap_ms=getattr(vtt_config, "coalesce_max_gap_ms", 500.0),
                    max_duration_seconds=getattr(
                        vtt_config, "coalesce_max_duration_seconds", 30.0
                    ),
                    max_characters=getattr(vtt_config, "coalesce_max_characters", 500),
                    preserve_cue_boundaries=getattr(
                        vtt_config, "preserve_cue_boundaries", True
                    ),
                )
            else:
                # Use defaults
                coalesce_config = CoalesceConfig(enabled=True)

        # Import VTT file
        print(f"\n[cyan]📥 Importing {selected_vtt.name}...[/cyan]")
        try:
            json_path = import_transcript(
                selected_vtt,
                output_dir=DIARISED_TRANSCRIPTS_DIR,
                coalesce_config=coalesce_config,
                overwrite=False,
            )

            # Load and display summary
            import json

            with open(json_path, "r", encoding="utf-8") as f:
                document = json.load(f)

            metadata = document.get("metadata", {})
            source = document.get("source", {})

            print(f"\n[green]✅ Successfully imported VTT file![/green]")
            print(f"\n[bold]Summary:[/bold]")
            print(f"  📄 JSON file: {json_path.name}")
            print(f"  📊 Segments: {metadata.get('segment_count', 0)}")
            print(f"  ⏱️  Duration: {metadata.get('duration_seconds', 0):.2f} seconds")
            print(f"  🗣️  Speakers: {metadata.get('speaker_count', 0)}")
            print(f"  📍 Source: {source.get('type', 'unknown')}")

            # Ask if user wants to proceed to analysis
            proceed = questionary.confirm(
                "\nWould you like to analyze this transcript now?",
                default=False,
            ).ask()

            if proceed:
                from transcriptx.cli.workflow_modules import (
                    run_single_analysis_workflow,
                )

                # Pass the imported transcript directly to analysis workflow
                run_single_analysis_workflow(transcript_path=json_path)

        except Exception as e:
            print(f"\n[red]❌ Error importing VTT file: {e}[/red]")
            import traceback

            traceback.print_exc()

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
    except Exception as e:
        print(f"\n[red]❌ Unexpected error: {e}[/red]")
        import traceback

        traceback.print_exc()
