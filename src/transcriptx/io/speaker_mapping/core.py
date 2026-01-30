"""Speaker mapping module."""

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from colorama import Fore, Style, init
from rich.console import Console

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.path_utils import resolve_file_path

# Lazy imports to avoid circular dependencies:
# - choose_mapping_action imported in load_or_create_speaker_map
# - offer_and_edit_tags imported in load_or_create_speaker_map

# Initialize colorama for cross-platform colored output
init(autoreset=True)

# Color cycle for speaker identification
# Each speaker gets a distinct color during the mapping process
COLOR_CYCLE = [
    Fore.CYAN,
    Fore.MAGENTA,
    Fore.YELLOW,
    Fore.GREEN,
    Fore.BLUE,
    Fore.LIGHTRED_EX,
]

console = Console()
logger = get_logger()


from .utils import SegmentRef, _extract_segment_times, _is_test_environment
from .interactive import _select_name_with_playback, GO_BACK_SENTINEL, EXIT_SENTINEL
from .database import _create_or_link_speaker_with_disambiguation


def update_transcript_json_with_speaker_names(
    transcript_path: str,
    speaker_map: Dict[str, str],
    speaker_id_to_db_id: Optional[Dict[str, int]] = None,
) -> None:
    """
    Update transcript JSON segments with speaker display names and optional DB IDs.
    """
    try:
        with open(transcript_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load transcript JSON for update: {e}")
        return

    segments = data.get("segments", [])
    if isinstance(segments, list):
        for seg in segments:
            speaker_id = seg.get("speaker")
            if speaker_id is None:
                continue
            if speaker_id in speaker_map:
                seg["speaker"] = speaker_map[speaker_id]
            if speaker_id_to_db_id and speaker_id in speaker_id_to_db_id:
                seg["speaker_db_id"] = speaker_id_to_db_id[speaker_id]

    data["speaker_map"] = speaker_map

    try:
        with open(transcript_path, "w") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        logger.warning(f"Failed to write updated transcript JSON: {e}")


def build_speaker_map(
    segments: List[Dict[str, Any]],
    speaker_map_path: str | None = None,
    review_mode: str = "all",
    existing_map: Dict[str, str] | None = None,
    batch_mode: bool = False,
    auto_generate: bool = False,
    transcript_path: Optional[str] = None,
    persist_speaker_records: bool = False,
) -> Dict[str, str] | None:
    """
    Build a speaker map by analyzing transcript segments.

    This function is the core of the speaker identification process. It
    analyzes transcript segments to identify unique speakers and allows
    users to assign human-readable names to them.

    The function supports multiple review modes:
    - "all": Review all speakers
    - "unidentified only": Only review speakers with system-generated names

    Args:
        segments: List of transcript segments to analyze
        speaker_map_path: Optional path to save the speaker map
        review_mode: Mode for reviewing speakers ("all" or "unidentified only")
        existing_map: Existing speaker map to build upon
        batch_mode: If True, auto-generate speaker names without prompts
        auto_generate: If True, auto-generate speaker names without prompts

    Returns:
        Dictionary mapping speaker IDs to human-readable names, or None if cancelled/exited

    Note:
        Speaker maps are only created via the interactive interface unless
        batch_mode or auto_generate is True, or running in test environment.
    """
    # Extract unique speaker IDs from segments (filter out None values)
    speaker_ids = sorted(
        set(
            seg["speaker"]
            for seg in segments
            if "speaker" in seg and seg["speaker"] is not None
        )
    )
    if not speaker_ids:
        # Check if all segments have None or missing speaker field
        segments_with_speaker = [
            seg for seg in segments if seg.get("speaker") is not None
        ]
        if not segments_with_speaker:
            console.print(
                f"❌ No speaker information found in transcript. All segments have speaker: None or missing speaker field.",
                style="red",
            )
            console.print(
                f"   This transcript may not have been diarized. Please run speaker diarization first.",
                style="yellow",
            )
        else:
            console.print(
                f"❌ No speakers found in transcript. Speaker map will not be created.",
                style="red",
            )
        return {}

    # Track database IDs for each speaker
    speaker_id_to_db_id: Dict[str, int] = {}

    # Auto-generate speaker names in batch mode, test mode, or when auto_generate is True
    if batch_mode or auto_generate or _is_test_environment():
        new_map = {}
        for i, speaker_id in enumerate(speaker_ids):
            # Use existing name if available, otherwise generate default name
            if existing_map and speaker_id in existing_map:
                new_map[speaker_id] = existing_map[speaker_id]
            else:
                new_map[speaker_id] = f"Speaker {i+1}"

        if transcript_path and new_map:
            update_transcript_json_with_speaker_names(
                transcript_path, new_map, speaker_id_to_db_id
            )
            logger.debug(
                f"Updated transcript JSON with speaker names: {transcript_path}"
                )

        return new_map

    speaker_map = existing_map or {}
    new_map = {}

    # Group text by speaker for review
    speaker_to_lines: Dict[str, List[SegmentRef]] = defaultdict(list)
    for seg in segments:
        if "speaker" in seg and "text" in seg:
            start, end = _extract_segment_times(seg)
            speaker_to_lines[seg["speaker"]].append(
                SegmentRef(text=str(seg["text"]), start=start, end=end)
            )

    audio_path: Optional[Path] = None
    if transcript_path:
        try:
            resolved = resolve_file_path(transcript_path, file_type="audio")
            audio_path = Path(resolved)
            if audio_path.exists():
                logger.debug(f"Audio file found for playback: {audio_path}")
            else:
                logger.warning(f"Audio file not found at resolved path: {audio_path}")
                audio_path = None
        except Exception as e:
            logger.warning(f"Failed to resolve audio path: {e}")
            audio_path = None
    if transcript_path and not audio_path:
        console.print("[yellow]⚠️ Audio not found; playback disabled.[/yellow]")
        logger.warning(f"Audio playback disabled for transcript: {transcript_path}")

    # Process each speaker
    # Use while loop to support going back to previous speakers
    i = 0
    while i < len(speaker_ids):
        speaker_id = speaker_ids[i]
        color = COLOR_CYCLE[i % len(COLOR_CYCLE)]
        existing_name = speaker_map.get(speaker_id)

        raw_system_name = str(speaker_id)

        # Skip speakers that don't need review in "unidentified only" mode
        if review_mode == "unidentified only":
            is_system_named = raw_system_name.lower().startswith(
                "unidentified"
            ) or raw_system_name.upper().startswith("SPEAKER_")
            has_been_renamed = speaker_map.get(speaker_id) != raw_system_name
            if not is_system_named or has_been_renamed:
                i += 1
                continue

        lines = speaker_to_lines[speaker_id]

        # Handle new speaker mapping (no existing map)
        if existing_map is None:
            total = len(lines)
            console.print(
                f"{color}\n📄 Speaker {speaker_id} — {total} lines (showing 10 at a time, press 'm' for more, 't' to toggle sort):{Style.RESET_ALL}"
            )
            name = _select_name_with_playback(
                speaker_id=str(speaker_id),
                segments=lines,
                existing_name=None,
                audio_path=audio_path,
            )
            # Handle "exit" request
            if name == EXIT_SENTINEL:
                console.print("[yellow]Exiting speaker mapping. Returning to menu...[/yellow]")
                return None
            # Handle "go back" request
            if name == GO_BACK_SENTINEL:
                if i > 0:
                    # Find the previous speaker that needs review
                    i -= 1
                    # Continue to previous speaker, but need to skip backwards through any skipped speakers
                    while i >= 0:
                        prev_speaker_id = speaker_ids[i]
                        prev_raw_name = str(prev_speaker_id)
                        if review_mode == "unidentified only":
                            prev_is_system_named = prev_raw_name.lower().startswith(
                                "unidentified"
                            ) or prev_raw_name.upper().startswith("SPEAKER_")
                            prev_has_been_renamed = speaker_map.get(prev_speaker_id) != prev_raw_name
                            if not prev_is_system_named or prev_has_been_renamed:
                                i -= 1
                                continue
                        # Found a valid previous speaker
                        break
                    if i < 0:
                        # Can't go back further, stay at current speaker
                        console.print("[yellow]⚠️ Already at first speaker.[/yellow]")
                        i = 0
                    continue
                else:
                    # Already at first speaker
                    console.print("[yellow]⚠️ Already at first speaker.[/yellow]")
                    continue
            elif name is None:
                new_map[speaker_id] = speaker_id
                i += 1
            elif name.strip():
                display_name = name.strip()
                db_id = None
                if persist_speaker_records:
                    db_id, display_name = _create_or_link_speaker_with_disambiguation(
                        display_name, batch_mode=batch_mode
                    )
                new_map[speaker_id] = display_name
                if db_id:
                    speaker_id_to_db_id[speaker_id] = db_id
                console.print(
                    f"[green]✅ {speaker_id} → {display_name} (saved)[/green]"
                )
                i += 1
            else:
                new_map[speaker_id] = speaker_id
                i += 1

        else:
            total = len(lines)
            console.print(
                f"{color}\n📄 Review: Speaker {speaker_id} — {total} lines (showing 10 at a time, press 'm' for more, 't' to toggle sort):{Style.RESET_ALL}"
            )
            name = _select_name_with_playback(
                speaker_id=str(speaker_id),
                segments=lines,
                existing_name=existing_name,
                audio_path=audio_path,
            )
            # Handle "exit" request
            if name == EXIT_SENTINEL:
                console.print("[yellow]Exiting speaker mapping. Returning to menu...[/yellow]")
                return None
            # Handle "go back" request
            if name == GO_BACK_SENTINEL:
                if i > 0:
                    # Find the previous speaker that needs review
                    i -= 1
                    # Continue to previous speaker, but need to skip backwards through any skipped speakers
                    while i >= 0:
                        prev_speaker_id = speaker_ids[i]
                        prev_raw_name = str(prev_speaker_id)
                        if review_mode == "unidentified only":
                            prev_is_system_named = prev_raw_name.lower().startswith(
                                "unidentified"
                            ) or prev_raw_name.upper().startswith("SPEAKER_")
                            prev_has_been_renamed = speaker_map.get(prev_speaker_id) != prev_raw_name
                            if not prev_is_system_named or prev_has_been_renamed:
                                i -= 1
                                continue
                        # Found a valid previous speaker
                        break
                    if i < 0:
                        # Can't go back further, stay at current speaker
                        console.print("[yellow]⚠️ Already at first speaker.[/yellow]")
                        i = 0
                    continue
                else:
                    # Already at first speaker
                    console.print("[yellow]⚠️ Already at first speaker.[/yellow]")
                    continue
            elif name is None or not name.strip():
                new_map[speaker_id] = existing_name or speaker_id
                i += 1
            else:
                display_name = name.strip()
                db_id = None
                if persist_speaker_records:
                    db_id, display_name = _create_or_link_speaker_with_disambiguation(
                        display_name, batch_mode=batch_mode
                    )
                new_map[speaker_id] = display_name
                if db_id:
                    speaker_id_to_db_id[speaker_id] = db_id
                console.print(
                    f"[green]✅ {speaker_id} → {display_name} (saved)[/green]"
                )
                i += 1

    # Always update transcript JSON if transcript_path is provided and we have a map
    # This ensures speaker names are persisted even when speaker_map_path is None
    if transcript_path and new_map:
        update_transcript_json_with_speaker_names(
            transcript_path, new_map, speaker_id_to_db_id
        )
        logger.debug(f"Updated transcript JSON with speaker names: {transcript_path}")

    return new_map


def save_speaker_map(*args, **kwargs) -> None:
    """
    DEPRECATED: Speaker map sidecars removed.

    Speaker names are now stored in transcript JSON metadata.
    Use build_speaker_map() to update transcript JSON directly.
    """
    raise RuntimeError(
        "Speaker map sidecars removed; speaker names are stored in transcript JSON metadata. "
        "Use build_speaker_map() to update transcript JSON directly."
    )


def load_speaker_map(*args, **kwargs) -> Dict[str, str] | None:
    """
    DEPRECATED: Speaker map sidecars removed.

    Use extract_speaker_map_from_transcript() to read from transcript JSON metadata,
    or get speaker info from segments directly.
    """
    raise RuntimeError(
        "Speaker map sidecars removed; speaker names are stored in transcript JSON metadata. "
        "Use extract_speaker_map_from_transcript() to read from transcript JSON, "
        "or get speaker info from segments directly."
    )

