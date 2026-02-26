"""WAV processing workflow main menu."""

from rich import print

from transcriptx.core.utils.logger import log_error
from transcriptx.utils.error_handling import graceful_exit

from . import check_ffmpeg_available, questionary

from .compress import _run_compress_workflow
from .convert import _run_convert_workflow
from .merge import _run_merge_workflow
from .preprocess import _run_preprocessing_workflow


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

        ffmpeg_available, error_msg = check_ffmpeg_available()
        if not ffmpeg_available:
            print(f"\n[red]❌ {error_msg}[/red]")
            print(
                "[yellow]Please install ffmpeg to use WAV processing features.[/yellow]"
            )
            print("[dim]On macOS: brew install ffmpeg[/dim]")
            print("[dim]On Linux: sudo apt-get install ffmpeg[/dim]")
            return

        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "〰️ Preprocessing",
                "🔄 Convert to MP3",
                "🔗 Merge Audio Files",
                "🗜️ Compress WAV Backups",
                "❌ Cancel",
            ],
        ).ask()

        if choice == "〰️ Preprocessing":
            _run_preprocessing_workflow()
        elif choice == "🔄 Convert to MP3":
            _run_convert_workflow()
        elif choice == "🔗 Merge Audio Files":
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
