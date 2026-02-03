from pathlib import Path
import glob
import questionary
from transcriptx.core.utils.config import get_config
import json
import os
import platform
from rich.console import Console
from transcriptx.core.utils.paths import (
    RECORDINGS_DIR,
    READABLE_TRANSCRIPTS_DIR,
    DIARISED_TRANSCRIPTS_DIR,
)
from transcriptx.core.utils.transcript_languages import (
    is_valid_language_code,
    normalize_language_code,
    transcript_exists_for_language,
)
from transcriptx.core.utils.path_utils import get_transcript_dir
from transcriptx.core.utils.logger import get_logger
from transcriptx.cli.audio import get_audio_duration
from transcriptx.utils.spinner import spinner
from transcriptx.cli.file_selection_interface import (
    FileSelectionConfig,
    select_files_interactive,
    format_audio_file,
    format_readable_transcript_file,
)

# Suppress CPR (Cursor Position Request) warning from prompt_toolkit
os.environ.setdefault("PROMPT_TOOLKIT_NO_CPR", "1")

console = Console()
logger = get_logger()

_TRANSCRIPT_PARENT_EXCLUSIONS = {
    "outputs",
    "analysis",
    "charts",
    "metadata",
    "stats",
    "sentiment",
    "emotion",
    "ner",
    "word_clouds",
    "networks",
}
_TRANSCRIPT_FILENAME_EXCLUSIONS = (
    "_summary.json",
    "_manifest.json",
    "_simplified_transcript.json",
)


def _normalize_allowed_exts(
    allowed_exts: tuple[str, ...] | None,
) -> tuple[str, ...] | None:
    if not allowed_exts:
        return None
    normalized: list[str] = []
    for ext in allowed_exts:
        if not ext:
            continue
        ext = ext.lower()
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.append(ext)
    return tuple(normalized) if normalized else None


def _make_absolute_path(path: Path) -> Path:
    return path.expanduser().absolute()


def _format_allowed_exts(allowed_exts: tuple[str, ...] | None) -> str:
    if not allowed_exts:
        return "any"
    return ", ".join(sorted(allowed_exts))


def _resolve_transcript_discovery_root(root: Path | None) -> Path | None:
    if root is not None:
        return Path(root)

    config_obj = get_config()
    default_folder = Path(config_obj.output.default_transcript_folder)
    if default_folder.exists():
        return default_folder

    diarised_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    if diarised_dir.exists():
        return diarised_dir

    return None


def _is_excluded_transcript_path(path: Path) -> bool:
    if path.name.endswith(_TRANSCRIPT_FILENAME_EXCLUSIONS):
        return True
    for parent in path.parents:
        if parent.name in _TRANSCRIPT_PARENT_EXCLUSIONS:
            return True
    return False


def discover_all_transcript_paths(root: Path | None = None) -> list[Path]:
    """
    Discover all transcript JSON paths using deterministic rules.

    Root selection:
      1) provided root
      2) config.output.default_transcript_folder if it exists
      3) DIARISED_TRANSCRIPTS_DIR if it exists
      4) else return []
    """
    root_path = _resolve_transcript_discovery_root(root)
    if root_path is None:
        return []

    transcripts_subdir = root_path / "transcripts"
    search_root = transcripts_subdir if transcripts_subdir.exists() else root_path

    resolved_paths: list[Path] = []
    seen: set[str] = set()
    for path in search_root.rglob("*.json"):
        if transcripts_subdir.exists() and transcripts_subdir != search_root:
            # Defensive: only search within transcripts/ when it exists.
            continue
        if not transcripts_subdir.exists() and _is_excluded_transcript_path(path):
            continue
        resolved = path.resolve()
        resolved_key = str(resolved)
        if resolved_key in seen:
            continue
        seen.add(resolved_key)
        resolved_paths.append(resolved)

    return sorted(resolved_paths, key=lambda p: str(p))


def _collect_paths_from_entries(
    entries: list[str],
    *,
    allowed_exts: tuple[str, ...] | None,
    must_exist: bool,
    allow_glob: bool,
) -> tuple[list[Path], list[tuple[str, str]]]:
    normalized_exts = _normalize_allowed_exts(allowed_exts)
    valid_paths: list[Path] = []
    invalid_entries: list[tuple[str, str]] = []
    seen: set[str] = set()

    for entry in entries:
        if not entry:
            continue
        raw_entry = entry.strip()
        if not raw_entry:
            continue

        expanded_entry = os.path.expanduser(raw_entry)
        is_glob = allow_glob and "*" in expanded_entry
        if is_glob:
            matched = glob.glob(expanded_entry, recursive=True)
            if not matched:
                invalid_entries.append((raw_entry, "No files match glob pattern"))
                continue
            candidate_paths = [Path(match) for match in matched]
        else:
            candidate_paths = [Path(expanded_entry)]

        for candidate in candidate_paths:
            absolute_path = _make_absolute_path(candidate)
            path_key = absolute_path.as_posix()
            if path_key in seen:
                continue
            seen.add(path_key)

            if must_exist and not absolute_path.exists():
                invalid_entries.append((raw_entry, "File does not exist"))
                continue
            if must_exist and not absolute_path.is_file():
                invalid_entries.append((raw_entry, "Path is not a file"))
                continue
            if normalized_exts and absolute_path.suffix.lower() not in normalized_exts:
                invalid_entries.append(
                    (
                        raw_entry,
                        f"File extension must be one of: {_format_allowed_exts(normalized_exts)}",
                    )
                )
                continue
            valid_paths.append(absolute_path)

    return valid_paths, invalid_entries


def _print_invalid_entries(invalid_entries: list[tuple[str, str]]) -> None:
    if not invalid_entries:
        return
    max_show = 5
    console.print("[yellow]⚠️ Some entries were invalid:[/yellow]")
    for entry, reason in invalid_entries[:max_show]:
        console.print(f"  [red]- {entry}[/red] [dim]({reason})[/dim]")
    remaining = len(invalid_entries) - max_show
    if remaining > 0:
        console.print(f"  [dim]...and {remaining} more[/dim]")


def _get_transcript_output_dir(language: str | None) -> Path:
    language_code = normalize_language_code(language)
    base_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    if language_code in (None, "en"):
        return base_dir
    return base_dir / language_code


def _prompt_language_code(default_value: str | None = None) -> tuple[str | None, bool]:
    prompt = (
        "Enter two-letter language code for transcription "
        "(e.g., en, fr, es, de, auto):"
    )
    while True:
        raw = questionary.text(prompt, default=default_value or "auto").ask()
        if raw is None:
            return None, True
        code = raw.strip().lower()
        if not code:
            return None, True
        if not is_valid_language_code(code):
            console.print(
                "[red]❌ Invalid language code. Use a two-letter code or 'auto'.[/red]"
            )
            continue
        return code, False


def _set_transcription_language(config) -> bool:
    current = getattr(config.transcription, "language", None) or "auto"
    language_code, cancelled = _prompt_language_code(current)
    if cancelled:
        return False
    normalized = normalize_language_code(language_code)
    config.transcription.language = normalized
    try:
        from transcriptx.core.config.persistence import save_project_config

        save_project_config(config.to_dict())
        label = normalized or "auto"
        console.print(
            f"[green]✅ Language set to {label} and saved to config[/green]"
        )
    except Exception as e:
        logger.warning(f"Could not save config: {e}")
        label = normalized or "auto"
        console.print(
            f"[yellow]⚠️  Language set to {label} for this session only[/yellow]"
        )
    return True


def _select_one_from_multiple_paths(paths: list[Path]) -> Path | None:
    choices = [questionary.Choice(title=str(path), value=path) for path in paths]
    choices.append(questionary.Choice(title="❌ Cancel", value=None))
    selected = questionary.select(
        "Multiple files matched. Select one:",
        choices=choices,
    ).ask()
    return selected if isinstance(selected, Path) else None


def prompt_for_file_path(
    allowed_exts: tuple[str, ...] | None = None,
    must_exist: bool = True,
    allow_glob: bool = False,
    prompt_text: str = "Enter file path:",
) -> Path | None:
    while True:
        raw = questionary.text(prompt_text).ask()
        if not raw:
            return None

        entries = [raw.strip()]
        valid_paths, invalid_entries = _collect_paths_from_entries(
            entries,
            allowed_exts=allowed_exts,
            must_exist=must_exist,
            allow_glob=allow_glob,
        )

        if len(valid_paths) == 1:
            return valid_paths[0]

        if len(valid_paths) > 1:
            selected = _select_one_from_multiple_paths(valid_paths)
            if selected:
                return selected
            return None

        _print_invalid_entries(invalid_entries)
        choice = questionary.select(
            "No valid files found.",
            choices=["Retry input", "Cancel"],
        ).ask()
        if choice != "Retry input":
            return None


def prompt_for_file_paths(
    allowed_exts: tuple[str, ...] | None = None,
    must_exist: bool = True,
    allow_glob: bool = True,
    prompt_text: str = "Enter file path(s) or glob pattern(s), comma-separated:",
) -> list[Path] | None:
    while True:
        raw = questionary.text(prompt_text).ask()
        if not raw:
            return None

        entries = [entry.strip() for entry in raw.split(",") if entry.strip()]
        if not entries:
            return None

        valid_paths, invalid_entries = _collect_paths_from_entries(
            entries,
            allowed_exts=allowed_exts,
            must_exist=must_exist,
            allow_glob=allow_glob,
        )

        if not valid_paths:
            _print_invalid_entries(invalid_entries)
            choice = questionary.select(
                "No valid files found.",
                choices=["Retry input", "Cancel"],
            ).ask()
            if choice == "Retry input":
                continue
            return None

        if invalid_entries:
            _print_invalid_entries(invalid_entries)
            choice = questionary.select(
                f"Continue with {len(valid_paths)} valid file(s)?",
                choices=["Continue", "Retry input", "Cancel"],
            ).ask()
            if choice == "Continue":
                return valid_paths
            if choice == "Retry input":
                continue
            return None

        return valid_paths


def _prompt_file_selection_mode() -> str | None:
    selection = questionary.select(
        "📂 How would you like to select files?",
        choices=[
            "📁 Explore file system",
            "⌨️  Provide file path directly",
            "❌ Cancel",
        ],
    ).ask()
    if selection == "📁 Explore file system":
        return "explore"
    if selection == "⌨️  Provide file path directly":
        return "direct"
    return None


def get_file_selection_mode(config=None):
    """
    Resolve file selection mode from config or by prompting.

    If config.input.file_selection_mode is "explore" or "direct", use that.
    If "prompt" or unset, show the selection prompt each time (including
    "Proceed to default folder", which uses existing default transcript/recording folder settings).
    Returns "explore", "direct", "default_folder", or None (cancel).
    """
    if config is None:
        config = get_config()
    mode = getattr(config.input, "file_selection_mode", "prompt")
    if mode == "explore":
        return "explore"
    if mode == "direct":
        return "direct"
    return _prompt_file_selection_mode()


def get_wav_folder_start_path(config) -> Path:
    """
    Get the first existing WAV folder path from configuration.

    Iterates through the configured WAV folders list and returns the first
    existing folder path. If none exist, uses fallback logic to find the
    nearest existing parent or defaults to /Volumes/ on macOS or RECORDINGS_DIR.

    Args:
        config: TranscriptXConfig instance

    Returns:
        Path to the first existing WAV folder, or a fallback path if none exist
    """
    if not config.input.wav_folders:
        # No folders configured, use default fallback
        if platform.system() == "Darwin":
            return Path("/Volumes/")
        else:
            return Path(RECORDINGS_DIR)

    # Try each configured folder in order
    for folder_path_str in config.input.wav_folders:
        folder_path = Path(folder_path_str)
        if folder_path.exists():
            return folder_path

        # If path doesn't exist, try to find nearest existing parent
        current_check = folder_path
        while current_check != current_check.parent:
            if current_check.exists():
                return current_check
            current_check = current_check.parent

    # None of the configured folders exist, use fallback
    if platform.system() == "Darwin":
        return Path("/Volumes/")
    else:
        return Path(RECORDINGS_DIR)


def get_recordings_folder_start_path(config) -> Path:
    """
    Get the first existing recordings folder path from configuration.

    Iterates through the configured recordings folders list and returns the first
    existing folder path. If none exist, uses fallback logic to find the
    nearest existing parent or defaults to RECORDINGS_DIR.

    Args:
        config: TranscriptXConfig instance

    Returns:
        Path to the first existing recordings folder, or a fallback path if none exist
    """
    if not config.input.recordings_folders:
        # No folders configured, use default fallback
        return Path(RECORDINGS_DIR)

    # Try each configured folder in order
    for folder_path_str in config.input.recordings_folders:
        folder_path = Path(folder_path_str)
        if folder_path.exists():
            return folder_path

        # If path doesn't exist, try to find nearest existing parent
        current_check = folder_path
        while current_check != current_check.parent:
            if current_check.exists():
                return current_check
            current_check = current_check.parent

    # None of the configured folders exist, use fallback
    return Path(RECORDINGS_DIR)


def _format_transcript_file_with_analysis(transcript_file: Path) -> str:
    """
    Format transcript file metadata for display, including analysis status.

    Args:
        transcript_file: Path to the transcript file

    Returns:
        Formatted string with file name, size, segment count, and analysis status
    """
    try:
        size_kb = transcript_file.stat().st_size / 1024
        has_analysis = _has_analysis_outputs(transcript_file)

        # Add ✨ prefix for unanalyzed files
        prefix = "✨ " if not has_analysis else ""

        try:
            with open(transcript_file) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "segments" in data:
                        segments = len(data["segments"])
                        return f"{prefix}📄 {transcript_file.name} ({size_kb:.1f} KB, {segments} segments)"
                    elif "text" in data:
                        text_length = len(data["text"])
                        return f"{prefix}📄 {transcript_file.name} ({size_kb:.1f} KB, {text_length} chars)"
                    else:
                        return f"{prefix}📄 {transcript_file.name} ({size_kb:.1f} KB)"
                else:
                    return f"{prefix}📄 {transcript_file.name} ({size_kb:.1f} KB)"
        except (json.JSONDecodeError, OSError, PermissionError):
            return f"{prefix}📄 {transcript_file.name} ({size_kb:.1f} KB)"
    except Exception:
        return f"📄 {transcript_file.name}"


def _has_analysis_outputs(transcript_file: Path) -> bool:
    """
    Check if a transcript file has been analyzed (has analysis outputs).

    Args:
        transcript_file: Path to the transcript JSON file

    Returns:
        True if analysis outputs exist, False otherwise
    """
    try:
        transcript_dir = Path(get_transcript_dir(str(transcript_file)))

        # If output directory doesn't exist, transcript hasn't been analyzed
        if not transcript_dir.exists():
            return False

        # Get all items in the output directory
        items = list(transcript_dir.iterdir())

        # Check if there are any analysis module subdirectories or stats files
        # Common analysis module directories: acts, sentiment, emotion, etc.
        # Also check for stats directory or comprehensive summary files
        analysis_indicators = [
            "acts",
            "sentiment",
            "emotion",
            "interactions",
            "ner",
            "topic_modeling",
            "semantic_similarity",
            "stats",
            "contagion",
            "conversation_loops",
            "entity_sentiment",
            "understandability",
        ]

        # Check for subdirectories that indicate analysis has been run
        for item in items:
            if item.is_dir() and item.name in analysis_indicators:
                return True

        # Check for comprehensive summary files (TXT)
        base_name = transcript_file.stem
        summary_files = [
            f"{base_name}_comprehensive_summary.txt",
        ]

        for item in items:
            if item.is_file() and item.name in summary_files:
                return True

        # If directory exists with multiple files/subdirs, likely analyzed
        return len(items) > 1

    except Exception:
        # If we can't check, assume not analyzed
        return False


def _process_transcript_paths(selected: list[Path]) -> list[Path] | None:
    processed_paths = []
    for selected_path in selected:
        # If VTT or SRT file, auto-import to JSON
        if selected_path.suffix.lower() in {".vtt", ".srt"}:
            from transcriptx.io.transcript_importer import ensure_json_artifact

            console.print(
                f"[cyan]📥 Importing transcript file: {selected_path.name}...[/cyan]"
            )
            try:
                json_path = ensure_json_artifact(selected_path)
                console.print(f"[green]✅ Converted to JSON: {json_path.name}[/green]")
                processed_paths.append(json_path)
            except Exception as e:
                console.print(
                    f"[red]❌ Error importing VTT file {selected_path.name}: {e}[/red]"
                )
                # Skip this file but continue with others
                continue
        else:
            processed_paths.append(selected_path)

    return processed_paths if processed_paths else None


def select_folder_interactive(start_path: Path | None = None) -> Path | None:
    if start_path is None:
        # Use the recordings directory as the default starting point
        config = get_config()
        start_path = Path(
            getattr(config.output, "default_audio_folder", RECORDINGS_DIR)
        )
        if not start_path.exists():
            start_path = Path(RECORDINGS_DIR)
    else:
        # If start_path is provided but doesn't exist, try to find nearest existing parent
        if not start_path.exists():
            # Walk up the directory tree to find the first existing parent
            current_check = start_path
            while current_check != current_check.parent:
                if current_check.exists():
                    start_path = current_check
                    break
                current_check = current_check.parent
            else:
                # If we've reached root and nothing exists, fall back to /Volumes/ on macOS
                # or the recordings directory as a safe default
                if platform.system() == "Darwin":
                    start_path = Path("/Volumes/")
                else:
                    start_path = Path(RECORDINGS_DIR)

    current_path = start_path
    while True:
        try:
            # Use os.scandir() which is more efficient than iterdir() on network mounts
            # and provides is_dir()/is_file() info without extra stat() calls
            folders = []
            files = []
            with os.scandir(current_path) as entries:
                for entry in entries:
                    if entry.name.startswith("."):
                        continue
                    path = Path(entry.path)
                    if entry.is_dir():
                        folders.append(path)
                    elif entry.is_file():
                        files.append(path)
        except PermissionError:
            console.print(f"[red]❌ Permission denied accessing {current_path}[/red]")
            return None
        except FileNotFoundError:
            # If current path doesn't exist, try to go up to parent
            if current_path != current_path.parent:
                current_path = current_path.parent
                continue
            else:
                console.print(f"[red]❌ Directory not found: {current_path}[/red]")
                return None
        except Exception as e:
            console.print(f"[red]❌ Error accessing {current_path}: {e}[/red]")
            return None

        # Check if current folder contains transcript files (.json) for informational purposes
        transcript_files = [f for f in files if f.suffix.lower() == ".json"]

        choices = []
        if current_path != current_path.parent:
            choices.append(questionary.Choice(title="📁 .. (Go up)", value=".."))
        choices.append(
            questionary.Choice(
                title=f"📍 Current: {current_path}", value=None, disabled=""
            )
        )
        choices.append(questionary.Choice(title="", value=None, disabled=""))
        for folder in sorted(folders):
            choices.append(questionary.Choice(title=f"📁 {folder.name}/", value=folder))
        # Always show file count, even if 0
        choices.append(
            questionary.Choice(title=f"📄 Files: {len(files)}", value=None, disabled="")
        )
        choices.append(questionary.Choice(title="", value=None, disabled=""))
        choices.append(
            questionary.Choice(title="✅ Select this folder", value="select")
        )
        choices.append(questionary.Choice(title="❌ Cancel", value="cancel"))
        console.print("\n[bold cyan]📂 Folder Navigation[/bold cyan]")
        console.print(f"[dim]Current location: {current_path}[/dim]")
        if transcript_files:
            console.print(
                f"[dim]ℹ️  Found {len(transcript_files)} transcript file(s) in this folder[/dim]"
            )
        try:
            selection = questionary.select(
                "Navigate to select a folder:",
                choices=choices,
            ).ask()
            if not selection:
                return None
            if selection == "select":
                return current_path
            if selection == "cancel":
                return None
            if selection == "..":
                current_path = current_path.parent
            elif isinstance(selection, Path):
                current_path = selection
        except KeyboardInterrupt:
            console.print("\n[cyan]Cancelled. Returning to previous menu.[/cyan]")
            return None


def select_audio_file_interactive() -> Path | None:
    audio_extensions = (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg")
    mode = get_file_selection_mode()
    if mode is None:
        return None
    if mode == "direct":
        while True:
            direct_path = prompt_for_file_path(
                allowed_exts=audio_extensions,
                allow_glob=False,
                prompt_text="Enter audio file path (e.g., ~/Downloads/audio.wav):",
            )
            if not direct_path:
                return None
            transcript_file = direct_path.with_suffix(".json")
            if transcript_file.exists():
                console.print(
                    f"[yellow]⚠️ Audio file already has transcript: {transcript_file.name}[/yellow]"
                )
                retry = questionary.select(
                    "Select a different file?",
                    choices=["Retry input", "Cancel"],
                ).ask()
                if retry == "Retry input":
                    continue
                return None
            return direct_path

    config_obj = get_config()
    # Use configurable recordings folders, fallback to default_audio_folder for backward compatibility
    start_path = get_recordings_folder_start_path(config_obj)
    if not start_path.exists():
        # Try default_audio_folder as fallback
        default_folder = Path(
            getattr(config_obj.output, "default_audio_folder", RECORDINGS_DIR)
        )
        if default_folder.exists():
            start_path = default_folder
        else:
            # Create the directory if it doesn't exist
            start_path.mkdir(parents=True, exist_ok=True)
    folder_path = select_folder_interactive(start_path=start_path)
    if not folder_path:
        return None
    audio_files: list[Path] = []
    for ext in audio_extensions:
        audio_files.extend(folder_path.glob(f"*{ext}"))
        audio_files.extend(folder_path.glob(f"*{ext.upper()}"))
    if not audio_files:
        console.print(f"[red]❌ No audio files found in {folder_path}[/red]")
        return None
    available_files = []
    for audio_file in audio_files:
        transcript_file = audio_file.with_suffix(".json")
        if not transcript_file.exists():
            available_files.append(audio_file)
    if not available_files:
        console.print(
            f"[yellow]⚠️ All audio files in {folder_path} have already been transcribed.[/yellow]"
        )
        return None

    # Use the new generic selection interface
    selection_config = FileSelectionConfig(
        multi_select=False,
        enable_playback=True,
        enable_rename=True,
        title="🎵 Audio File Selection",
        current_path=folder_path,
        metadata_formatter=format_audio_file,
    )

    selected = select_files_interactive(available_files, selection_config)
    if selected and len(selected) > 0:
        return selected[0]
    return None


def select_transcript_file_interactive() -> Path | None:
    """
    Select a single transcript file interactively.

    For selecting multiple transcripts, use select_transcript_files_interactive() instead.
    """
    mode = get_file_selection_mode()
    if mode is None:
        return None
    if mode == "direct":
        selected = prompt_for_file_path(
            allowed_exts=(".json", ".vtt", ".srt"),
            allow_glob=False,
            prompt_text="Enter transcript file path:",
        )
        if not selected:
            return None
        processed = _process_transcript_paths([selected])
        return processed[0] if processed else None

    config_obj = get_config()
    default_folder = Path(config_obj.output.default_transcript_folder)
    if not default_folder.exists():
        default_folder.mkdir(parents=True, exist_ok=True)
    if mode == "default_folder":
        folder_path = default_folder
    else:
        folder_path = select_folder_interactive(start_path=default_folder)
        if not folder_path:
            return None
    transcript_files = discover_all_transcript_paths(folder_path)
    transcript_files.extend(list(folder_path.rglob("*.vtt")))
    transcript_files.extend(list(folder_path.rglob("*.srt")))
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in transcript_files:
        resolved = path.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resolved)
    transcript_files = sorted(deduped, key=lambda p: p.name.lower())
    if not transcript_files:
        console.print(
            f"[red]❌ No transcript files (.json/.vtt/.srt) found in {folder_path}[/red]"
        )
        return None

    selection_config = FileSelectionConfig(
        multi_select=False,
        enable_playback=False,
        enable_rename=True,
        title="📄 Transcript File Selection",
        current_path=folder_path,
        metadata_formatter=_format_transcript_file_with_analysis,
    )

    selected = select_files_interactive(transcript_files, selection_config)
    if not selected or len(selected) == 0:
        return None
    processed = _process_transcript_paths(selected)
    return processed[0] if processed else None


def select_transcript_files_interactive() -> list[Path] | None:
    """
    Select one or more transcript files interactively with multi-select support.

    Returns:
        List of selected transcript file paths, or None if cancelled
    """
    mode = get_file_selection_mode()
    if mode is None:
        return None
    if mode == "direct":
        selected = prompt_for_file_paths(
            allowed_exts=(".json", ".vtt", ".srt"),
            allow_glob=True,
            prompt_text="Enter transcript file path(s) or glob pattern(s), comma-separated:",
        )
        if not selected:
            return None
        return _process_transcript_paths(selected)

    config_obj = get_config()
    default_folder = Path(config_obj.output.default_transcript_folder)
    if not default_folder.exists():
        # Create the directory if it doesn't exist
        default_folder.mkdir(parents=True, exist_ok=True)
    if mode == "default_folder":
        folder_path = default_folder
    else:
        folder_path = select_folder_interactive(start_path=default_folder)
        if not folder_path:
            return None
    # Include .json via shared discovery rules; add .vtt/.srt for interactive only
    transcript_files = discover_all_transcript_paths(folder_path)
    transcript_files.extend(list(folder_path.rglob("*.vtt")))
    transcript_files.extend(list(folder_path.rglob("*.srt")))
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in transcript_files:
        resolved = path.resolve()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resolved)
    transcript_files = sorted(deduped, key=lambda p: p.name.lower())
    if not transcript_files:
        console.print(
            f"[red]❌ No transcript files (.json/.vtt/.srt) found in {folder_path}[/red]"
        )
        return None

    # Use the new generic selection interface with multi-select enabled
    selection_config = FileSelectionConfig(
        multi_select=True,
        enable_playback=False,
        enable_rename=True,
        enable_select_all=True,
        title="📄 Transcript File Selection (Multi-select enabled)",
        current_path=folder_path,
        metadata_formatter=_format_transcript_file_with_analysis,
    )

    selected = select_files_interactive(transcript_files, selection_config)
    if not selected or len(selected) == 0:
        return None

    return _process_transcript_paths(selected)


def select_readable_transcript_file_interactive() -> Path | None:
    """Select a readable transcript file (CSV or TXT) for analysis."""
    mode = get_file_selection_mode()
    if mode is None:
        return None
    if mode == "direct":
        return prompt_for_file_path(
            allowed_exts=(".csv", ".txt"),
            allow_glob=False,
            prompt_text="Enter readable transcript file path (CSV/TXT):",
        )

    config_obj = get_config()
    default_folder = Path(
        getattr(
            config_obj.output,
            "default_readable_transcript_folder",
            READABLE_TRANSCRIPTS_DIR,
        )
    )
    if not default_folder.exists():
        # Create the directory if it doesn't exist
        default_folder.mkdir(parents=True, exist_ok=True)
    folder_path = select_folder_interactive(start_path=default_folder)
    if not folder_path:
        return None

    # Look for both CSV and TXT files
    transcript_files = list(folder_path.glob("*.csv")) + list(folder_path.glob("*.txt"))
    transcript_files = sorted(transcript_files, key=lambda p: p.name.lower())

    if not transcript_files:
        console.print(
            f"[red]❌ No readable transcript files (.csv/.txt) found in {folder_path}[/red]"
        )
        return None

    # Use the new generic selection interface
    selection_config = FileSelectionConfig(
        multi_select=False,
        enable_playback=False,
        enable_rename=True,
        title="📄 Readable Transcript File Selection",
        current_path=folder_path,
        metadata_formatter=format_readable_transcript_file,
    )

    selected = select_files_interactive(transcript_files, selection_config)
    if selected and len(selected) > 0:
        return selected[0]
    return None


def select_audio_for_whisperx_transcription() -> list[Path] | None:
    """
    Select one or more audio files from configured recordings folders that don't already have corresponding transcripts.
    This function specifically handles the WhisperX integration requirement.
    
    Returns:
        List of selected audio file paths, or None if cancelled. For single file selection,
        returns a list with one item.
    """
    from transcriptx.core.utils.config import get_config

    audio_extensions = (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg")
    mode = get_file_selection_mode()
    if mode is None:
        return None

    config = get_config()
    recordings_dir = get_recordings_folder_start_path(config)
    transcripts_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    transcripts_output_dir = _get_transcript_output_dir(
        getattr(config.transcription, "language", None)
    )

    # Ensure directories exist
    recordings_dir.mkdir(parents=True, exist_ok=True)
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    if mode == "direct":
        while True:
            selected_paths = prompt_for_file_paths(
                allowed_exts=audio_extensions,
                allow_glob=True,
                prompt_text="Enter audio file path(s) or glob pattern(s), comma-separated:",
            )
            if not selected_paths:
                return None

            available_files: list[Path] = []
            invalid_entries: list[tuple[str, str]] = []
            files_with_existing_transcripts: list[Path] = []
            for audio_file in selected_paths:
                if transcript_exists_for_language(
                    audio_file.stem, getattr(config.transcription, "language", None)
                ):
                    invalid_entries.append(
                        (str(audio_file), "Transcript already exists")
                    )
                    files_with_existing_transcripts.append(audio_file)
                    continue
                available_files.append(audio_file)

            if not available_files:
                _print_invalid_entries(invalid_entries)
                if files_with_existing_transcripts:
                    choice = questionary.select(
                        "No valid files available (already transcribed).",
                        choices=["🔄 Overwrite and re-transcribe", "Retry input", "Cancel"],
                    ).ask()
                    if choice == "🔄 Overwrite and re-transcribe":
                        if not _set_transcription_language(config):
                            return None
                        transcripts_output_dir = _get_transcript_output_dir(
                            getattr(config.transcription, "language", None)
                        )
                        return files_with_existing_transcripts
                    elif choice == "Retry input":
                        continue
                    else:
                        return None
                else:
                    retry = questionary.select(
                        "No valid files available (already transcribed).",
                        choices=["Retry input", "Cancel"],
                    ).ask()
                    if retry == "Retry input":
                        continue
                    return None

            if invalid_entries:
                _print_invalid_entries(invalid_entries)
                choice = questionary.select(
                    f"Some files already have transcripts. What would you like to do?",
                    choices=[
                        f"Continue with {len(available_files)} new file(s) only",
                        "🔄 Overwrite existing and include all files",
                        "Retry input",
                        "Cancel",
                    ],
                ).ask()
                if choice == f"Continue with {len(available_files)} new file(s) only":
                    return available_files
                elif choice == "🔄 Overwrite existing and include all files":
                    if not _set_transcription_language(config):
                        return None
                    transcripts_output_dir = _get_transcript_output_dir(
                        getattr(config.transcription, "language", None)
                    )
                    return selected_paths
                elif choice == "Retry input":
                    continue
                else:
                    return None

            return available_files

    # Find all audio files in recordings directory
    audio_files = []
    for ext in audio_extensions:
        audio_files.extend(recordings_dir.glob(f"*{ext}"))
        audio_files.extend(recordings_dir.glob(f"*{ext.upper()}"))

    if not audio_files:
        console.print(f"[red]❌ No audio files found in {recordings_dir}[/red]")
        console.print(f"[dim]Supported formats: {', '.join(audio_extensions)}[/dim]")
        return None

    # Filter out audio files that already have transcripts
    # Check diarised transcripts directory
    available_files = []
    files_with_existing_transcripts = []
    for audio_file in audio_files:
        if transcript_exists_for_language(
            audio_file.stem, getattr(config.transcription, "language", None)
        ):
            files_with_existing_transcripts.append(audio_file)
        else:
            available_files.append(audio_file)

    if not available_files:
        if files_with_existing_transcripts:
            console.print(
                f"[yellow]⚠️ All audio files in {recordings_dir} have already been transcribed.[/yellow]"
            )
            console.print(f"[dim]Transcripts are stored in: {transcripts_dir}[/dim]")
            choice = questionary.select(
                "What would you like to do?",
                choices=["🔄 Overwrite and re-transcribe all", "Cancel"],
            ).ask()
            if choice == "🔄 Overwrite and re-transcribe all":
                if not _set_transcription_language(config):
                    return None
                transcripts_output_dir = _get_transcript_output_dir(
                    getattr(config.transcription, "language", None)
                )
                available_files = files_with_existing_transcripts
            else:
                return None
        else:
            console.print(
                f"[yellow]⚠️ All audio files in {recordings_dir} have already been transcribed.[/yellow]"
            )
            console.print(f"[dim]Transcripts are stored in: {transcripts_dir}[/dim]")
            return None

    # Sort by name for consistent ordering
    available_files = sorted(available_files, key=lambda p: p.name.lower())

    # Debug: Log how many files are available
    logger.debug(f"Found {len(available_files)} available audio files for WhisperX transcription")
    
    # Provide user feedback before showing selection menu
    console.print(f"\n[bold cyan]🎤 WhisperX Transcription - Available Audio Files[/bold cyan]")
    console.print(f"[dim]Found {len(available_files)} audio files ready for transcription[/dim]")
    console.print(f"[dim]Recordings directory: {recordings_dir}[/dim]")
    console.print(f"[dim]Transcripts will be saved to: {transcripts_output_dir}[/dim]")
    
    # Ensure any previous output is flushed before showing the selection menu
    import sys
    sys.stdout.flush()
    sys.stderr.flush()

    # Use the new generic selection interface
    # The interactive interface will display the files with full metadata and playback support
    selection_config = FileSelectionConfig(
        multi_select=True,
        enable_playback=True,
        enable_rename=True,
        enable_select_all=True,
        title="🎤 WhisperX Transcription - Audio File Selection",
        current_path=recordings_dir,
        metadata_formatter=format_audio_file,
        toggle_hidden_files=files_with_existing_transcripts,
        toggle_hidden_label="Show transcribed",
        toggle_hidden_key="t",
    )

    try:
        selected = select_files_interactive(available_files, selection_config)
        if selected and len(selected) > 0:
            return selected
        return None
    except Exception as e:
        # Log the error and provide user feedback
        logger.error(f"Error in file selection interface: {e}", exc_info=True)
        console.print(f"[red]❌ Error displaying file selection menu: {e}[/red]")
        console.print("[yellow]⚠️ Falling back to simple file selection...[/yellow]")
        # Fallback to a simpler selection method
        if available_files:
            from rich.prompt import Prompt
            console.print(f"\n[bold]Available audio files:[/bold]")
            for idx, file_path in enumerate(available_files, 1):
                console.print(f"  {idx}. {file_path.name}")
            try:
                choice = Prompt.ask("\nEnter file number(s) separated by commas (or 'q' to cancel)", default="q")
                if choice.lower() == 'q':
                    return None
                # Parse multiple file selections
                selected_indices = [int(x.strip()) - 1 for x in choice.split(',')]
                selected_files = [available_files[idx] for idx in selected_indices if 0 <= idx < len(available_files)]
                if selected_files:
                    return selected_files
                else:
                    console.print("[red]❌ Invalid file number[/red]")
                    return None
            except (ValueError, KeyboardInterrupt):
                return None
        return None


def validate_wav_file(wav_path: Path) -> tuple[bool, str | None]:
    """
    Validate that a WAV file exists and is readable.

    Args:
        wav_path: Path to the WAV file to validate

    Returns:
        tuple[bool, str | None]: (is_valid, error_message)
    """
    if not wav_path.exists():
        return False, f"File does not exist: {wav_path}"

    if not wav_path.is_file():
        return False, f"Path is not a file: {wav_path}"

    if wav_path.suffix.lower() != ".wav":
        return False, f"File is not a WAV file (extension: {wav_path.suffix})"

    try:
        file_size = wav_path.stat().st_size
        if file_size == 0:
            return False, "File is empty (0 bytes)"
        if file_size < 1024:  # Less than 1KB
            return (
                False,
                f"File is suspiciously small ({file_size} bytes), may be corrupted",
            )
    except OSError as e:
        return False, f"Cannot access file: {str(e)}"

    # Check if file is readable
    try:
        with open(wav_path, "rb") as f:
            f.read(1)  # Try to read at least 1 byte
    except PermissionError:
        return False, f"Permission denied: {wav_path}"
    except Exception as e:
        return False, f"Cannot read file: {str(e)}"

    return True, None


def select_wav_files_interactive(start_path: Path | None = None) -> list[Path] | None:
    """
    Select one or more WAV files interactively, starting from /Volumes/.

    Uses directory navigation similar to select_folder_interactive() but
    filters for WAV files and allows multi-select.

    Args:
        start_path: Starting directory path (defaults to /Volumes/)

    Returns:
        list[Path] | None: List of selected WAV file paths, or None if cancelled
    """
    mode = get_file_selection_mode()
    if mode is None:
        return None
    if mode == "direct":
        return prompt_for_file_paths(
            allowed_exts=(".wav",),
            allow_glob=True,
            prompt_text="Enter WAV file path(s) or glob pattern(s), comma-separated:",
        )

    if start_path is None:
        start_path = Path("/Volumes/")

    # Navigate to folder containing WAV files
    current_path = start_path

    while True:
        try:
            # Use os.scandir() which is more efficient than iterdir() on network mounts
            # and provides is_dir()/is_file() info without extra stat() calls
            folders = []
            files = []
            with os.scandir(current_path) as entries:
                for entry in entries:
                    if entry.name.startswith("."):
                        continue
                    path = Path(entry.path)
                    if entry.is_dir():
                        folders.append(path)
                    elif entry.is_file():
                        files.append(path)
        except PermissionError:
            console.print(f"[red]❌ Permission denied accessing {current_path}[/red]")
            return None
        except FileNotFoundError:
            console.print(f"[red]❌ Directory not found: {current_path}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]❌ Error accessing {current_path}: {e}[/red]")
            return None

        # Filter for WAV files (excluding hidden files starting with '.')
        wav_files = [f for f in files if f.suffix.lower() == ".wav"]

        # If we're in a folder with WAV files, show them for selection
        if wav_files:
            # Default merge order: filesystem creation order (oldest first)
            def _creation_sort_key(path: Path) -> tuple[float, str]:
                try:
                    st = path.stat()
                    # Prefer birth time (macOS/BSD), else ctime (Windows creation, Unix metadata change)
                    t = getattr(st, "st_birthtime", st.st_ctime)
                    return (t, path.name.lower())
                except OSError:
                    return (0.0, path.name.lower())

            wav_files = sorted(wav_files, key=_creation_sort_key)

            # Use the new generic selection interface
            selection_config = FileSelectionConfig(
                multi_select=True,
                enable_playback=True,
                enable_rename=True,
                enable_select_all=True,
                title="🎵 WAV File Selection",
                current_path=current_path,
                metadata_formatter=format_audio_file,
                validator=validate_wav_file,
            )

            selected_files = select_files_interactive(wav_files, selection_config)
            return selected_files

        # No WAV files in current directory, show navigation menu
        nav_choices = []
        if current_path != current_path.parent:
            nav_choices.append(questionary.Choice(title="📁 .. (Go up)", value=".."))
        nav_choices.append(
            questionary.Choice(
                title=f"📍 Current: {current_path}", value=None, disabled=""
            )
        )
        nav_choices.append(questionary.Choice(title="", value=None, disabled=""))

        for folder in sorted(folders):
            nav_choices.append(
                questionary.Choice(title=f"📁 {folder.name}/", value=folder)
            )

        # Always show file counts
        if wav_files:
            nav_choices.append(
                questionary.Choice(
                    title=f"🎵 WAV files: {len(wav_files)}", value=None, disabled=""
                )
            )
        nav_choices.append(
            questionary.Choice(
                title=f"📄 Total files: {len(files)}", value=None, disabled=""
            )
        )

        nav_choices.append(questionary.Choice(title="", value=None, disabled=""))
        nav_choices.append(questionary.Choice(title="❌ Cancel", value="cancel"))

        console.print("\n[bold cyan]📂 Folder Navigation[/bold cyan]")
        console.print(f"[dim]Current location: {current_path}[/dim]")
        console.print(
            "[yellow]No WAV files found in this folder. Navigate to find WAV files.[/yellow]"
        )

        try:
            selection = questionary.select(
                "Navigate to find WAV files:",
                choices=nav_choices,
            ).ask()

            if not selection or selection == "cancel":
                return None

            if selection == "..":
                current_path = current_path.parent
            elif isinstance(selection, Path):
                current_path = selection
        except KeyboardInterrupt:
            console.print("\n[cyan]Cancelled. Returning to previous menu.[/cyan]")
            return None


def select_single_audio_file_for_preprocessing(
    start_path: Path | None = None,
) -> Path | None:
    """
    Select a single audio file (MP3, WAV, etc.) for preprocessing.

    Does not filter by transcript existence. Supports direct path or explore.

    Returns:
        Selected file path, or None if cancelled
    """
    mode = get_file_selection_mode()
    if mode is None:
        return None
    if mode == "direct":
        return prompt_for_file_path(
            allowed_exts=(".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"),
            must_exist=True,
            allow_glob=False,
            prompt_text="Enter audio file path (e.g. .../recordings/file.mp3):",
        )

    config = get_config()
    current_path = start_path or get_recordings_folder_start_path(config)
    if not current_path.exists():
        current_path = Path(RECORDINGS_DIR)

    audio_extensions = (".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg")

    while True:
        try:
            folders = []
            files = []
            with os.scandir(current_path) as entries:
                for entry in entries:
                    if entry.name.startswith("."):
                        continue
                    path = Path(entry.path)
                    if entry.is_dir():
                        folders.append(path)
                    elif entry.is_file():
                        files.append(path)
        except (PermissionError, FileNotFoundError) as e:
            console.print(f"[red]❌ Error accessing {current_path}: {e}[/red]")
            return None
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            return None

        audio_files = [
            f for f in files
            if f.suffix.lower() in audio_extensions
        ]

        if audio_files:
            def _creation_sort_key(p: Path) -> tuple[float, str]:
                try:
                    st = p.stat()
                    t = getattr(st, "st_birthtime", st.st_ctime)
                    return (t, p.name.lower())
                except OSError:
                    return (0.0, p.name.lower())

            audio_files = sorted(audio_files, key=_creation_sort_key)
            selection_config = FileSelectionConfig(
                multi_select=False,
                enable_playback=True,
                enable_rename=True,
                title="🎵 Select audio file to preprocess",
                current_path=current_path,
                metadata_formatter=format_audio_file,
            )
            selected = select_files_interactive(audio_files, selection_config)
            if selected and len(selected) > 0:
                return selected[0]
            return None

        nav_choices = []
        if current_path != current_path.parent:
            nav_choices.append(questionary.Choice(title="📁 .. (Go up)", value=".."))
        nav_choices.append(
            questionary.Choice(
                title=f"📍 Current: {current_path}", value=None, disabled=""
            )
        )
        nav_choices.append(questionary.Choice(title="", value=None, disabled=""))
        for folder in sorted(folders):
            nav_choices.append(
                questionary.Choice(title=f"📁 {folder.name}/", value=folder)
            )
        nav_choices.append(questionary.Choice(title="", value=None, disabled=""))
        nav_choices.append(questionary.Choice(title="❌ Cancel", value="cancel"))

        console.print("\n[bold cyan]📂 Folder Navigation[/bold cyan]")
        console.print(f"[dim]Current location: {current_path}[/dim]")
        console.print(
            "[yellow]No audio files (MP3/WAV/etc.) here. Navigate to find one.[/yellow]"
        )

        try:
            selection = questionary.select(
                "Navigate to find an audio file:",
                choices=nav_choices,
            ).ask()

            if not selection or selection == "cancel":
                return None
            if selection == "..":
                current_path = current_path.parent
            elif isinstance(selection, Path):
                current_path = selection
        except KeyboardInterrupt:
            console.print("\n[cyan]Cancelled.[/cyan]")
            return None


def reorder_files_interactive(files: list[Path]) -> list[Path] | None:
    """
    Interactive file reordering interface.

    Allows user to reorder a list of files before merging or processing.

    Args:
        files: List of file paths to reorder

    Returns:
        Reordered list of file paths, or None if cancelled
    """
    if not files or len(files) < 2:
        return files

    current_order = list(files)

    while True:
        console.print("\n[bold cyan]📋 Reorder Files[/bold cyan]")
        console.print(
            "[dim]Current order (files will be merged in this sequence):[/dim]\n"
        )

        # Load file metadata (size, duration) with spinner — can be slow on USB
        with spinner("Loading file info..."):
            file_lines: list[str] = []
            for idx, file_path in enumerate(current_order, 1):
                try:
                    size_mb = file_path.stat().st_size / (1024 * 1024)
                    duration = get_audio_duration(file_path)
                    if duration:
                        duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"
                        file_lines.append(
                            f"  {idx}. {file_path.name} ({size_mb:.1f} MB, {duration_str})"
                        )
                    else:
                        file_lines.append(f"  {idx}. {file_path.name} ({size_mb:.1f} MB)")
                except Exception:
                    file_lines.append(f"  {idx}. {file_path.name}")

        for line in file_lines:
            console.print(line)

        # Show reordering options
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "⬆️ Move file up",
                "⬇️ Move file down",
                "🔄 Swap two files",
                "✅ Done (use this order)",
                "❌ Cancel",
            ],
        ).ask()

        if not choice or choice == "❌ Cancel":
            return None

        if choice == "✅ Done (use this order)":
            return current_order

        if choice == "⬆️ Move file up":
            # Select file to move up
            file_choices = [
                questionary.Choice(title=f"{idx}. {file_path.name}", value=idx - 1)
                for idx, file_path in enumerate(current_order, 1)
            ]
            # Don't allow moving first file up
            file_choices[0].disabled = "Already at top"

            selected_idx = questionary.select(
                "Select file to move up:",
                choices=file_choices,
            ).ask()

            if selected_idx is not None and selected_idx > 0:
                # Swap with previous
                current_order[selected_idx], current_order[selected_idx - 1] = (
                    current_order[selected_idx - 1],
                    current_order[selected_idx],
                )

        elif choice == "⬇️ Move file down":
            # Select file to move down
            file_choices = [
                questionary.Choice(title=f"{idx}. {file_path.name}", value=idx - 1)
                for idx, file_path in enumerate(current_order, 1)
            ]
            # Don't allow moving last file down
            file_choices[-1].disabled = "Already at bottom"

            selected_idx = questionary.select(
                "Select file to move down:",
                choices=file_choices,
            ).ask()

            if selected_idx is not None and selected_idx < len(current_order) - 1:
                # Swap with next
                current_order[selected_idx], current_order[selected_idx + 1] = (
                    current_order[selected_idx + 1],
                    current_order[selected_idx],
                )

        elif choice == "🔄 Swap two files":
            # Select first file
            file_choices_1 = [
                questionary.Choice(title=f"{idx}. {file_path.name}", value=idx - 1)
                for idx, file_path in enumerate(current_order, 1)
            ]

            idx1 = questionary.select(
                "Select first file to swap:",
                choices=file_choices_1,
            ).ask()

            if idx1 is None:
                continue

            # Select second file (exclude first selection)
            file_choices_2 = [
                questionary.Choice(title=f"{idx}. {file_path.name}", value=idx - 1)
                for idx, file_path in enumerate(current_order, 1)
                if idx - 1 != idx1
            ]

            idx2 = questionary.select(
                "Select second file to swap:",
                choices=file_choices_2,
            ).ask()

            if idx2 is not None:
                # Swap the files
                current_order[idx1], current_order[idx2] = (
                    current_order[idx2],
                    current_order[idx1],
                )
