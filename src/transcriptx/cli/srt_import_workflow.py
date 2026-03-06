"""
SRT import workflow for TranscriptX.
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


def run_srt_import_workflow() -> None:
    """
    Workflow for explicitly importing SRT files.
    """
    with graceful_exit():
        _run_srt_import_workflow_impl()


def _run_srt_import_workflow_impl() -> None:
    try:
        print("\n[bold cyan]📄 Import SRT File[/bold cyan]")

        config = get_config()
        default_folder = Path(config.output.default_transcript_folder)
        if not default_folder.exists():
            default_folder.mkdir(parents=True, exist_ok=True)

        folder_path = select_folder_interactive(start_path=default_folder)
        if not folder_path:
            print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
            return

        srt_files = list(folder_path.glob("*.srt"))
        srt_files = sorted(srt_files, key=lambda p: p.name.lower())

        if not srt_files:
            print(f"\n[red]❌ No SRT files found in {folder_path}[/red]")
            return

        if len(srt_files) == 1:
            selected_srt = srt_files[0]
            print(f"\n[dim]Selected: {selected_srt.name}[/dim]")
        else:
            import questionary

            choices = [f.name for f in srt_files]
            selected_name = questionary.select(
                "Select SRT file to import:",
                choices=choices,
            ).ask()

            if not selected_name:
                print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
                return

            selected_srt = folder_path / selected_name

        import questionary

        coalesce_enabled = questionary.confirm(
            "Enable segment coalescing? (merge adjacent subtitles)",
            default=False,
        ).ask()

        coalesce_config = None
        if coalesce_enabled:
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
                coalesce_config = CoalesceConfig(enabled=True)

        print(f"\n[cyan]📥 Importing {selected_srt.name}...[/cyan]")
        try:
            json_path = import_transcript(
                selected_srt,
                output_dir=DIARISED_TRANSCRIPTS_DIR,
                coalesce_config=coalesce_config,
                overwrite=False,
            )

            import json

            with open(json_path, "r", encoding="utf-8") as handle:
                document = json.load(handle)

            metadata = document.get("metadata", {})
            source = document.get("source", {})

            print("\n[green]✅ Successfully imported SRT file![/green]")
            print("\n[bold]Summary:[/bold]")
            print(f"  📄 JSON file: {json_path.name}")
            print(f"  📊 Segments: {metadata.get('segment_count', 0)}")
            print(f"  ⏱️  Duration: {metadata.get('duration_seconds', 0):.2f} seconds")
            print(f"  🗣️  Speakers: {metadata.get('speaker_count', 0)}")
            print(f"  📍 Source: {source.get('type', 'unknown')}")

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

        except Exception as exc:
            print(f"\n[red]❌ Error importing SRT file: {exc}[/red]")
            import traceback

            traceback.print_exc()

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
    except Exception as exc:
        print(f"\n[red]❌ Unexpected error: {exc}[/red]")
        import traceback

        traceback.print_exc()


"""
SRT import workflow for TranscriptX.
"""

from rich.console import Console


console = Console()


def run_srt_import_workflow() -> None:
    with graceful_exit():
        _run_srt_import_workflow_impl()


def _run_srt_import_workflow_impl() -> None:
    try:
        print("\n[bold cyan]📄 Import SRT File[/bold cyan]")

        config = get_config()
        default_folder = Path(config.output.default_transcript_folder)
        if not default_folder.exists():
            default_folder.mkdir(parents=True, exist_ok=True)

        folder_path = select_folder_interactive(start_path=default_folder)
        if not folder_path:
            print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
            return

        srt_files = list(folder_path.glob("*.srt"))
        srt_files = sorted(srt_files, key=lambda p: p.name.lower())
        if not srt_files:
            print(f"\n[red]❌ No SRT files found in {folder_path}[/red]")
            return

        if len(srt_files) == 1:
            selected_srt = srt_files[0]
            print(f"\n[dim]Selected: {selected_srt.name}[/dim]")
        else:
            import questionary

            choices = [f.name for f in srt_files]
            selected_name = questionary.select(
                "Select SRT file to import:",
                choices=choices,
            ).ask()
            if not selected_name:
                print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
                return
            selected_srt = folder_path / selected_name

        import questionary

        coalesce_enabled = questionary.confirm(
            "Enable segment coalescing? (merge adjacent subtitles)",
            default=False,
        ).ask()

        coalesce_config = None
        if coalesce_enabled:
            config_obj = get_config()
            srt_config = getattr(config_obj, "srt_import", None)
            if srt_config:
                coalesce_config = CoalesceConfig(
                    enabled=True,
                    max_gap_ms=getattr(srt_config, "coalesce_max_gap_ms", 500.0),
                    max_duration_seconds=getattr(
                        srt_config, "coalesce_max_duration_seconds", 30.0
                    ),
                    max_characters=getattr(srt_config, "coalesce_max_characters", 500),
                    preserve_cue_boundaries=getattr(
                        srt_config, "preserve_cue_boundaries", True
                    ),
                )
            else:
                coalesce_config = CoalesceConfig(enabled=True)

        print(f"\n[cyan]📥 Importing {selected_srt.name}...[/cyan]")
        json_path = import_transcript(
            selected_srt,
            output_dir=DIARISED_TRANSCRIPTS_DIR,
            coalesce_config=coalesce_config,
            overwrite=False,
        )

        import json

        with open(json_path, "r", encoding="utf-8") as handle:
            document = json.load(handle)

        metadata = document.get("metadata", {})
        source = document.get("source", {})

        print("\n[green]✅ Successfully imported SRT file![/green]")
        print("\n[bold]Summary:[/bold]")
        print(f"  📄 JSON file: {json_path.name}")
        print(f"  📊 Segments: {metadata.get('segment_count', 0)}")
        print(f"  ⏱️  Duration: {metadata.get('duration_seconds', 0):.2f} seconds")
        print(f"  🗣️  Speakers: {metadata.get('speaker_count', 0)}")
        print(f"  📍 Source: {source.get('type', 'unknown')}")

        proceed = questionary.confirm(
            "\nWould you like to analyze this transcript now?",
            default=False,
        ).ask()
        if proceed:
            from transcriptx.cli.workflow_modules import run_single_analysis_workflow

            # Pass the imported transcript directly to analysis workflow
            run_single_analysis_workflow(transcript_path=json_path)

    except KeyboardInterrupt:
        print("\n[cyan]Cancelled. Returning to main menu.[/cyan]")
    except Exception as e:
        print(f"\n[red]❌ Error importing SRT file: {e}[/red]")
        import traceback

        traceback.print_exc()
