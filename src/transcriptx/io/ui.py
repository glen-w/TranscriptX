import os
import sys
from pathlib import Path

import questionary
from rich.console import Console
from colorama import Fore
from transcriptx.core.utils.paths import RECORDINGS_DIR
from transcriptx.core.utils.config import get_config
from transcriptx.cli.file_selection_utils import get_recordings_folder_start_path

console = Console()

SPEAKER_COLORS = [
    Fore.CYAN,
    Fore.MAGENTA,
    Fore.YELLOW,
    Fore.GREEN,
    Fore.BLUE,
    Fore.LIGHTRED_EX,
    Fore.LIGHTCYAN_EX,
]


def get_color_for_speaker(speaker_id):
    index = int(speaker_id.split("_")[-1]) if speaker_id.split("_")[-1].isdigit() else 0
    return SPEAKER_COLORS[index % len(SPEAKER_COLORS)]


def prompt_for_audio_file(audio_dir=None):
    try:
        # Use configurable recordings folders if audio_dir not provided
        if audio_dir is None:
            config = get_config()
            audio_dir = str(get_recordings_folder_start_path(config))
        elif audio_dir == RECORDINGS_DIR:
            # If default is used, check if config has custom folders
            config = get_config()
            if config.input.recordings_folders:
                audio_dir = str(get_recordings_folder_start_path(config))

        audio_exts = (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg")
        files = []

        for f in os.listdir(audio_dir):
            if f.lower().endswith(audio_exts):
                base = os.path.splitext(f)[0]
                transcript_path = os.path.join(audio_dir, base + ".json")
                if not os.path.exists(transcript_path):
                    files.append(f)

        if not files:
            print("🎧 No untranscribed audio files found in this folder.")
            return None

        choice = questionary.select(
            "🎧 Choose an audio file to transcribe:",
            choices=sorted(files),
        ).ask()

        if not choice:
            return None

        return str(Path(audio_dir) / choice)

    except KeyboardInterrupt:
        print("\n❌ Cancelled by user. Exiting...")
        sys.exit(0)


def prompt_for_transcript_folder() -> str:
    folder = questionary.path(
        "📁 Choose transcript folder:",
        default=str(Path.cwd()),
        only_directories=True,
    ).ask()
    if not folder or not os.path.isdir(folder):
        print("❌ Invalid or no folder selected.")
        sys.exit(1)
    return folder


def prompt_for_transcript_file():
    json_files = [f for f in os.listdir() if f.endswith(".json")]
    if not json_files:
        raise FileNotFoundError("No .json files found in the selected folder.")
    return questionary.select("📄 Choose a transcript file:", choices=json_files).ask()


def choose_mapping_action(unidentified_count, batch_mode=False, has_tags=False):
    # In batch mode, return a default choice to avoid interactive prompts
    if batch_mode:
        return "✅ Proceed with current speaker mapping"

    choices = [
        "✅ Proceed with current speaker mapping",
        "🔁 Review all speaker labels",
    ]
    if unidentified_count > 0:
        choices.append(f"🎭 Review unidentified speakers only ({unidentified_count})")
    if has_tags:
        choices.append("🏷️ Manage tags")
    choices.append("🔄 Start speaker mapping over from scratch")

    return questionary.select(
        "🎛️ What would you like to do?",
        choices=choices,
    ).ask()


def show_banner():
    console.print("========================================", style="bold blue")
    console.print("  🎤  TranscriptX - Transcript Analyzer  🎤", style="bold cyan")
    console.print("========================================", style="bold blue")


def prompt_main_choice():
    choice = questionary.select(
        "What would you like to do?",
        choices=[
            "Transcribe audio file",
            "Analyze transcript file",
            "Exit",
        ],
    ).ask()
    if choice == "Transcribe audio file":
        return "transcribe"
    if choice == "Analyze transcript file":
        return "analyze"
    return "exit"


def prompt_audio_path():
    return questionary.path(
        "Enter path to audio file:",
        only_files=True,
    ).ask()


def prompt_transcript_path():
    return questionary.path(
        "Enter path to transcript (.json) file:",
        only_files=True,
    ).ask()


def display_progress(current: int, total: int, description: str = "Progress"):
    """
    Display a progress bar for long-running operations.

    Args:
        current: Current progress value
        total: Total value to reach
        description: Description of the operation
    """
    if total <= 0:
        return

    percentage = (current / total) * 100
    bar_length = 30
    filled_length = int(bar_length * current // total)

    bar = "█" * filled_length + "░" * (bar_length - filled_length)

    print(
        f"\r{description}: |{bar}| {percentage:.1f}% ({current}/{total})",
        end="",
        flush=True,
    )

    if current >= total:
        print()  # New line when complete
