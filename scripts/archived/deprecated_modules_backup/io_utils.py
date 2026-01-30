"""
I/O Utilities for TranscriptX.

⚠️ DEPRECATED MODULE - MIGRATION IN PROGRESS ⚠️

This module is being phased out in favor of the new centralized transcriptx.io module.
**This module will be removed in v0.3.0**. Please migrate to the new module for all new code.

Migration Guide:
    OLD (deprecated):                    NEW (preferred):
    from transcriptx.io_utils import *    from transcriptx.io import (
                                              load_segments,
                                              load_transcript,
                                              load_transcript_data,
                                              load_speaker_map,
                                              save_json,
                                              save_csv,
                                          )

Current Status:
- This module still has 23+ active imports across the codebase
- Migration is in progress but not yet complete
- Functions are re-exported with deprecation warnings (see end of file)
- New code should use transcriptx.io module instead

This module provides comprehensive input/output utilities for TranscriptX,
handling file operations, speaker mapping, transcript processing, and data
export. It serves as the central hub for all file system interactions and
data transformation operations.

Key Features:
- Transcript file loading and parsing
- Speaker mapping and identification
- Interactive speaker name assignment
- Data export in multiple formats (JSON, CSV, TXT)
- Batch processing support
- File validation and error handling

The module includes both interactive and batch modes, allowing for
automated processing while still supporting manual speaker identification
when needed.

Core Functions:
1. File Loading: Load transcripts and speaker maps from JSON files
2. Speaker Mapping: Convert system IDs to human-readable names
3. Data Export: Save results in multiple formats for analysis
4. Validation: Ensure data integrity and proper file formats
5. Batch Processing: Handle multiple files efficiently

This module is essential for the TranscriptX pipeline as it handles
all data ingress and egress operations, ensuring consistent file
formats and proper speaker identification across all analysis modules.
"""

import csv
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import questionary
from colorama import Fore, Style, init
from rich.console import Console

from transcriptx.core.utils.config import get_config
from transcriptx.utils.text_utils import is_named_speaker, strip_emojis
from transcriptx.io.ui import choose_mapping_action
from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.core.utils.path_utils import get_base_name, get_transcript_dir, get_speaker_map_path, find_existing_speaker_map as find_existing_speaker_map_core
# Note: extract_tags is imported lazily inside load_or_create_speaker_map to avoid circular dependency
from transcriptx.cli.tag_workflow import offer_and_edit_tags, store_tags_in_database
from transcriptx.core.utils.file_rename import rename_transcript_after_speaker_mapping

# Initialize colorama for cross-platform colored output
# This ensures consistent colored output across different operating systems
init(autoreset=True)

# Color cycle for speaker identification
# Each speaker gets a distinct color during the mapping process
# This helps users visually distinguish between different speakers
COLOR_CYCLE = [
    Fore.CYAN,
    Fore.MAGENTA,
    Fore.YELLOW,
    Fore.GREEN,
    Fore.BLUE,
    Fore.LIGHTRED_EX,
]

console = Console()


def get_segments(path: str) -> list[dict[str, Any]]:
    """
    Load and extract segments from a transcript JSON file.

    This function handles different JSON structures that might be present
    in transcript files. It can process both direct segment lists and
    nested structures with a 'segments' key.

    Args:
        path: Path to the transcript JSON file

    Returns:
        List of segment dictionaries containing transcript data

    Note:
        The function is flexible and can handle:
        - Files with {"segments": [...]} structure
        - Files that are direct lists of segments
        - WhisperX format with words arrays (extracts speaker from words)
        - Returns empty list for invalid formats

        This flexibility allows TranscriptX to work with transcripts
        from different sources and formats without requiring strict
        standardization of the input files.
    """
    with open(path) as f:
        data = json.load(f)
    
    segments = []
    if isinstance(data, dict):
        segments = data.get("segments", [])
    elif isinstance(data, list):
        segments = data  # assume it's already a list of segments
    
    # Process segments to handle WhisperX format with words arrays
    processed_segments = []
    for segment in segments:
        if isinstance(segment, dict):
            # Check if this is a WhisperX format segment with words array
            if "words" in segment and "speaker" not in segment:
                # Extract speaker from words array (use most common speaker)
                words = segment.get("words", [])
                if words:
                    # Count speaker occurrences
                    speaker_counts = {}
                    for word in words:
                        if isinstance(word, dict) and "speaker" in word:
                            speaker = word["speaker"]
                            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
                    
                    # Use the most common speaker
                    if speaker_counts:
                        most_common_speaker = max(speaker_counts, key=speaker_counts.get)
                        # Create a new segment with speaker field
                        processed_segment = segment.copy()
                        processed_segment["speaker"] = most_common_speaker
                        processed_segments.append(processed_segment)
                    else:
                        # No speaker found in words, assign a default speaker
                        processed_segment = segment.copy()
                        processed_segment["speaker"] = "UNKNOWN_SPEAKER"
                        processed_segments.append(processed_segment)
                else:
                    # No words array, assign a default speaker
                    processed_segment = segment.copy()
                    processed_segment["speaker"] = "UNKNOWN_SPEAKER"
                    processed_segments.append(processed_segment)
            else:
                processed_segments.append(segment)
    
    return processed_segments


def load_transcript(path: str) -> Any:
    """
    Load a complete transcript file as JSON.

    This function loads the entire transcript file without any processing,
    useful when you need access to the full file structure including
    metadata, configuration, or other non-segment data.

    Args:
        path: Path to the transcript JSON file

    Returns:
        The complete JSON data from the file

    Note:
        Unlike get_segments(), this function preserves the complete
        file structure, including any metadata, configuration, or
        additional fields that might be present in the transcript file.
        This is useful for modules that need access to file-level
        information or custom fields.
    """
    with open(path) as f:
        return json.load(f)


def extract_speaker_text(
    segments: list[dict[str, Any]], speaker_map: dict[str, str]
) -> dict[str, list[str]]:
    """
    Extract and group text by speaker from transcript segments.

    This function processes transcript segments and organizes them by
    speaker, filtering out unnamed speakers and applying speaker mapping.
    It's useful for generating speaker-specific analysis or summaries.

    Args:
        segments: List of transcript segments
        speaker_map: Mapping from speaker IDs to human-readable names

    Returns:
        Dictionary mapping speaker names to lists of their text segments

    Note:
        Only includes speakers that have been properly named (not system
        placeholders like "SPEAKER_01" or "Unidentified"). This ensures
        that analysis results focus on actual human speakers rather than
        system artifacts.

        The function is commonly used for:
        - Generating speaker-specific word clouds
        - Creating speaker summaries and statistics
        - Analyzing individual speaker patterns
        - Preparing data for speaker-focused analysis modules
    """
    grouped: dict[str, list[str]] = {}
    for seg in segments:
        spk = seg.get("speaker")
        if not spk:
            continue
        name = speaker_map.get(spk, spk)
        if name and is_named_speaker(name):
            grouped.setdefault(name, []).append(seg.get("text", ""))
    return grouped


def find_existing_speaker_map(transcript_path: str) -> str | None:
    """
    Find existing speaker map in outputs directory.
    
    This function delegates to the core path_utils implementation
    which includes improved search logic for renamed transcripts.
    
    Args:
        transcript_path: Path to the transcript JSON file
        
    Returns:
        Path to existing speaker map if found, None otherwise
    """
    # Use the improved implementation from path_utils
    return find_existing_speaker_map_core(transcript_path)


def get_default_speaker_map_path(transcript_path):
    """
    Get the default speaker map path for a transcript.
    
    This function first checks for existing speaker maps in the outputs directory,
    then falls back to the standard location next to the transcript file.
    
    Args:
        transcript_path: Path to the transcript JSON file
        
    Returns:
        Path to the speaker map file in the correct location
        
    Example:
        Input: /path/to/meeting.json
        Output: /path/to/meeting/meeting_speaker_map.json
    """
    # First, check if there's an existing speaker map in outputs
    existing_path = find_existing_speaker_map(transcript_path)
    if existing_path:
        return existing_path
    
    # Fall back to the standard location
    from transcriptx.core.utils.path_utils import get_base_name, get_transcript_dir
    base_name = get_base_name(transcript_path)
    transcript_dir = get_transcript_dir(transcript_path)
    return os.path.join(transcript_dir, f"{base_name}_speaker_map.json")


def validate_speaker_map_path(speaker_map_path: str, transcript_path: str) -> str:
    """
    Validate and correct speaker map path to ensure it's in the right location.
    
    This function first checks for existing speaker maps in the outputs directory,
    then falls back to the standard location next to the transcript file.
    
    Args:
        speaker_map_path: Current speaker map path
        transcript_path: Path to the transcript file
        
    Returns:
        Corrected speaker map path
        
    Raises:
        ValueError: If the path is invalid or cannot be corrected
    """
    # First, check if there's an existing speaker map in outputs
    existing_path = find_existing_speaker_map(transcript_path)
    if existing_path:
        return existing_path
    
    # Fall back to the standard location
    expected_path = get_speaker_map_path(transcript_path)
    
    # If the current path is already correct, return it
    if speaker_map_path == expected_path:
        return speaker_map_path
    
    # If the current path exists and is not empty, warn about potential conflict
    if os.path.exists(speaker_map_path):
        try:
            with open(speaker_map_path, 'r') as f:
                content = f.read().strip()
                if content and content != '{}':
                    console.print(f"⚠️ WARNING: Found existing speaker map at {speaker_map_path}")
                    console.print(f"   Expected location: {expected_path}")
                    console.print(f"   This may indicate a path construction bug.")
        except Exception:
            pass
    
    # Return the correct path
    return expected_path




def load_or_create_speaker_map(
    segments: list[dict[str, Any]], 
    speaker_map_path: str, 
    transcript_path: str | None = None,
    batch_mode: bool = False
) -> dict[str, str] | None:
    """
    Handle speaker name mapping with intelligent reuse and revision.

    This function manages the speaker mapping process, which is crucial for
    converting system-generated speaker IDs (like "SPEAKER_01") into
    human-readable names. It automatically loads existing speaker maps or
    launches interactive identification when needed.

    The function can:
    - Load existing speaker maps automatically
    - Launch interactive identification when speaker map is missing
    - Allow users to revise existing mappings
    - Create new mappings from scratch

    Args:
        segments: List of transcript segments to analyze
        speaker_map_path: Path where speaker map should be saved/loaded
        transcript_path: Path to the transcript file (for validation)

    Returns:
        Dictionary mapping speaker IDs to human-readable names, or None if cancelled

    Note:
        The speaker mapping process is critical for meaningful analysis because:
        - It converts system IDs to human-readable names
        - It enables speaker-specific analysis and reporting
        - It improves the readability of output files and visualizations
        - It allows for cross-session speaker tracking

        The function provides a user-friendly interface for speaker identification
        with automatic handling of existing speaker maps.
    """
    # CRITICAL FIX: Validate and correct speaker map path to prevent corruption
    # This prevents the bug where speaker maps are saved in wrong locations
    if transcript_path:
        speaker_map_path = validate_speaker_map_path(speaker_map_path, transcript_path)
    else:
        # Fallback validation for when transcript_path is not available
        if not speaker_map_path.endswith("_speaker_map.json") and not os.path.exists(speaker_map_path):
            console.print(f"⚠️ WARNING: Cannot validate speaker map path without transcript_path")
            console.print(f"   Current path: {speaker_map_path}")

    if os.path.exists(speaker_map_path):
        with open(speaker_map_path) as f:
            return json.load(f)

    # If no speaker map exists, prompt user to create one or cancel
    # Skip prompt in batch mode since user has already confirmed they want speaker identification
    if not os.path.exists(speaker_map_path):
        if not batch_mode:
            console.print(f"❌ No speaker map found at {speaker_map_path}.", style="red")
            console.print("A speaker map is required to proceed with analysis.")
            create_now = questionary.confirm(
                "Would you like to identify speakers now (interactive mapping)?"
            ).ask()
            if not create_now:
                console.print("[yellow]Returning to main menu. Speaker mapping is required before analysis.[/yellow]")
                return None
        # In batch mode or after user confirms, proceed to build speaker map interactively

    # Extract tags early (before speaker mapping)
    # This allows tag management to be available during speaker mapping
    auto_tags = []
    tag_details = {}
    if not batch_mode:
        try:
            # Lazy import to avoid circular dependency
            from transcriptx.core.analysis.tag_extraction import extract_tags
            tag_result = extract_tags(segments)
            auto_tags = tag_result.get("tags", [])
            tag_details = tag_result.get("tag_details", {})
        except Exception as e:
            console.print(f"[dim]Note: Could not extract tags: {e}[/dim]")

    # Build new speaker map
    # Create a fresh speaker mapping from the transcript segments
    speaker_map = build_speaker_map(segments, speaker_map_path)

    # Track final tags (will be updated during tag management)
    final_tags = auto_tags.copy()
    final_tag_details = tag_details.copy()

    # Interactive review loop
    # Allow users to review and revise the speaker mapping
    while True:
        # Count unidentified speakers
        # Track how many speakers still need proper identification
        unidentified_count = sum(
            1
            for speaker_id in speaker_map
            if (
                speaker_id.lower().startswith("unidentified")
                or speaker_id.upper().startswith("SPEAKER_")
            )
            and speaker_map.get(speaker_id) == speaker_id
        )

        # Check if we have tags to show in menu
        has_tags = len(auto_tags) > 0 or len(final_tags) > 0

        # Get user action choice
        # Present options based on the current state of speaker identification
        action = choose_mapping_action(unidentified_count, batch_mode=batch_mode, has_tags=has_tags)

        # Handle different action choices
        # Process the user's selection and take appropriate action
        if "review all" in action.lower():
            speaker_map = build_speaker_map(
                segments,
                speaker_map_path,
                review_mode="all",
                existing_map=speaker_map,
            )
        elif "unidentified" in action.lower():
            speaker_map = build_speaker_map(
                segments,
                speaker_map_path,
                review_mode="unidentified only",
                existing_map=speaker_map,
            )
        elif "manage tags" in action.lower() or "🏷️" in action or "tags" in action.lower():
            # Show tag management interface using centralized workflow
            # auto_prompt=False since we're already in a menu
            if transcript_path:
                tag_result = offer_and_edit_tags(
                    transcript_path,
                    batch_mode=batch_mode,
                    auto_prompt=False
                )
                if tag_result:
                    final_tags = tag_result.get("tags", [])
                    final_tag_details = tag_result.get("tag_details", {})
        elif "start speaker mapping over" in action.lower():
            console.print("🔄 Starting over: clearing speaker names...\n")
            speaker_map = build_speaker_map(segments, speaker_map_path)
            # Reset tags when starting over
            try:
                # Lazy import to avoid circular dependency
                from transcriptx.core.analysis.tag_extraction import extract_tags
                tag_result = extract_tags(segments)
                auto_tags = tag_result.get("tags", [])
                tag_details = tag_result.get("tag_details", {})
                final_tags = auto_tags.copy()
                final_tag_details = tag_details.copy()
            except Exception:
                pass
            continue
        elif "proceed" in action.lower():
            console.print("✅ Proceeding with current speaker mapping.\n")
            break

    # After speaker mapping is complete, show tag management automatically
    if not batch_mode and transcript_path:
        # Use centralized workflow (auto_prompt=True to show prompt)
        tag_result = offer_and_edit_tags(
            transcript_path,
            batch_mode=batch_mode,
            auto_prompt=True
        )
        if tag_result:
            final_tags = tag_result.get("tags", [])
            final_tag_details = tag_result.get("tag_details", {})

    return speaker_map


def load_speaker_map(transcript_path: str) -> dict[str, str]:
    """
    Load a speaker map based on a transcript JSON path.

    This function automatically constructs the path to the speaker map file
    based on the transcript file location. It first checks for existing
    speaker maps in the outputs directory, then falls back to the standard location.

    Args:
        transcript_path: Path to the transcript JSON file

    Returns:
        Dictionary mapping speaker IDs to human-readable names

    Note:
        If no speaker map is found, returns an empty dictionary.
        The function also handles speaker ID normalization (e.g., "1" -> "SPEAKER_01").
    """
    map_path = get_default_speaker_map_path(transcript_path)
    if not os.path.exists(map_path):
        console.print(f"⚠️ No speaker map found at {map_path}")
        return {}
    with open(map_path) as f:
        raw_map = json.load(f)
    return {
        (f"SPEAKER_{int(k):02}" if str(k).isdigit() else k): v
        for k, v in raw_map.items()
    }


def build_speaker_map(
    segments: list[dict[str, Any]],
    speaker_map_path: str | None = None,
    review_mode: str = "all",
    existing_map: dict[str, str] | None = None,
) -> dict[str, str]:
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

    Returns:
        Dictionary mapping speaker IDs to human-readable names

    Note:
        Speaker maps are only created via the interactive interface.
    """
    # Extract unique speaker IDs from segments
    speaker_ids = sorted(set(seg["speaker"] for seg in segments if "speaker" in seg))
    if not speaker_ids:
        console.print(f"❌ No speakers found in transcript. Speaker map will not be created.", style="red")
        return {}

    speaker_map = existing_map or {}
    new_map = {}

    # Group text by speaker for review
    speaker_to_lines = defaultdict(list)
    for seg in segments:
        if "speaker" in seg and "text" in seg:
            speaker_to_lines[seg["speaker"]].append(seg["text"])

    # Process each speaker
    for i, speaker_id in enumerate(speaker_ids):
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
                continue

        lines = speaker_to_lines[speaker_id]

        # Handle new speaker mapping (no existing map)
        if existing_map is None:
            total = len(lines)
            shown = 0
            batch = 10

            console.print(
                f"{color}\n📄 Speaker {speaker_id} — {total} lines available:{Style.RESET_ALL}"
            )

            # Show lines in batches for user review
            while shown < total:
                for line in lines[shown : shown + batch]:
                    console.print(f"{color}➤  {line.strip()}{Style.RESET_ALL}")
                shown += batch

                remaining = total - shown
                if remaining > 0:
                    user_input = (
                        questionary.text(
                            f"\n🔎 Press Enter to see 10 more lines ({remaining} left), or type a name to assign:",
                        )
                        .ask()
                        .strip()
                    )
                    if user_input:
                        new_map[speaker_id] = user_input
                        break
                else:
                    break

            if speaker_id not in new_map:
                name = (
                    questionary.text(f"\n💬 Enter name for speaker '{speaker_id}':")
                    .ask()
                    .strip()
                )
                new_map[speaker_id] = name if name else speaker_id

        else:

            def line_score(text):
                tokens = text.lower().split()
                return len(set(tokens)) + 0.1 * len(tokens)

            lines = sorted(lines, key=line_score, reverse=True)
            total = len(lines)

            if total <= 10:
                console.print(
                    f"{color}\n📄 Review: Speaker {speaker_id} — {total} lines (no paging needed):{Style.RESET_ALL}"
                )
                for line in lines:
                    console.print(f"{color}➤  {line.strip()}{Style.RESET_ALL}")
            else:
                shown = 0
                batch = 10
                console.print(
                    f"{color}\n📄 Review: Speaker {speaker_id} — {total} lines (most unique first):{Style.RESET_ALL}"
                )

                while shown < total:
                    for line in lines[shown : shown + batch]:
                        console.print(f"{color}➤  {line.strip()}{Style.RESET_ALL}")
                    shown += batch

                    if shown >= total:
                        console.print("✅ No more lines.")

                    prompt_msg = f"\n💬 Enter name for speaker '{speaker_id}'"
                    if existing_name:
                        prompt_msg += f" (Enter = keep '{existing_name}', or type 'more' to continue):"

                    user_input = questionary.text(prompt_msg).ask().strip()

                    if not user_input:
                        new_map[speaker_id] = existing_name or speaker_id
                        break
                    if user_input.lower() == "more":
                        continue
                    new_map[speaker_id] = user_input
                    break

            if speaker_id not in new_map:
                prompt_msg = f"\n💬 Enter name for speaker '{speaker_id}'"
                if existing_name:
                    prompt_msg += f" (press Enter to keep '{existing_name}')"
                prompt_msg += ":"
                name = questionary.text(prompt_msg).ask().strip()
                new_map[speaker_id] = name if name else existing_name or speaker_id

    if speaker_map_path:
        # CRITICAL FIX: Ensure directory exists and path is valid
        os.makedirs(os.path.dirname(speaker_map_path), exist_ok=True)
        
        # Validate the speaker map before saving to prevent corruption
        if new_map:
            with open(speaker_map_path, "w") as f:
                json.dump(new_map, f, indent=2)
            console.print(f"✅ Speaker map saved to: {speaker_map_path}")
            
            # Update processing state if we can determine transcript path
            # Try to infer from speaker_map_path
            try:
                from transcriptx.core.utils.path_utils import get_canonical_base_name
                from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
                canonical_base = get_canonical_base_name(speaker_map_path.replace("_speaker_map.json", ""))
                # Try to find transcript path
                transcript_candidates = [
                    Path(DIARISED_TRANSCRIPTS_DIR) / f"{canonical_base}.json",
                    Path(DIARISED_TRANSCRIPTS_DIR) / f"{canonical_base}_transcript_diarised.json",
                ]
                for candidate in transcript_candidates:
                    if candidate.exists():
                        from transcriptx.io.speaker_mapping import _update_state_with_speaker_map
                        _update_state_with_speaker_map(str(candidate), speaker_map_path)
                        break
            except Exception:
                # If we can't update state, that's okay - it's not critical
                pass
        else:
            console.print(f"⚠️ WARNING: Attempting to save empty speaker map to: {speaker_map_path}")
            # Don't save empty maps to prevent corruption
    return new_map


def load_segments_and_speaker_map(path):
    with open(path) as f:
        data = json.load(f)

    segments = data["segments"]

    for seg in segments:
        speaker = seg.get("speaker")
        if isinstance(speaker, int) or (isinstance(speaker, str) and speaker.isdigit()):
            seg["speaker"] = f"SPEAKER_{int(speaker):02}"

    # Load external speaker map from sidecar file using centralized logic
    input_path = Path(path)
    base_name = input_path.stem
    map_path = get_default_speaker_map_path(path)

    if os.path.exists(map_path):
        with open(map_path) as f:
            raw_map = json.load(f)
    else:
        console.print(f"⚠️ Speaker map file not found at {map_path}")
        raw_map = {}

    # Normalize keys like SPEAKER_01, 02, etc.
    speaker_map = {
        (f"SPEAKER_{int(k):02}" if str(k).isdigit() else k): v
        for k, v in raw_map.items()
    }

    return segments, speaker_map


def load_segments(path):
    with open(path) as f:
        data = json.load(f)
    return data["segments"]


def write_transcript_files(
    segments: list, speaker_map: dict, base_name: str, out_dir: str, format_time
) -> tuple:
    transcript_path = os.path.join(out_dir, f"{base_name}_transcript_readable.txt")
    csv_path = os.path.join(out_dir, f"{base_name}_transcript_readable.csv")

    with open(transcript_path, "w") as f_txt, open(csv_path, "w") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(["Speaker", "Timestamp", "Text"])

        prev_speaker = None
        buffer = []
        start_time = None

        for seg in segments:
            spk = seg.get("speaker")
            name = speaker_map.get(spk, spk)
            text = seg.get("text", "").strip()
            pause = seg.get("pause", 0)
            timestamp = format_time(seg.get("start", 0))

            writer.writerow([name, timestamp, text])

            if name != prev_speaker:
                if prev_speaker and buffer:
                    f_txt.write(f"\n🗣️ {prev_speaker} ⏱️ {start_time}\n")
                    f_txt.write("".join(buffer) + "\n")
                    buffer = []
                start_time = timestamp
                prev_speaker = name

            if pause >= 2:
                f_txt.write(f"\n⏸️  {int(pause)} sec pause\n")

            buffer.append(text.strip() + "\n\n")

        if prev_speaker and buffer:
            f_txt.write(f"\n🗣️ {prev_speaker} ⏱️ {start_time}\n")
            f_txt.write("".join(buffer) + "\n")

    return transcript_path, csv_path


def save_transcript(data: list, path: str) -> None:
    """
    Saves the transcript list back into a JSON file, inside a 'segments' wrapper if needed.
    """
    # Ensure the directory exists before writing the file
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    if isinstance(data, list):
        content = {"segments": data}
    else:
        content = data
    with open(path, "w") as f:
        json.dump(content, f, indent=2)


def save_json(data: dict, path: str):
    import numpy as np

    def convert_np(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
        return str(obj) if hasattr(obj, "__str__") else obj

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=convert_np)


def save_csv(rows: list[list], path: str, header: list[str] | None = None) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        if header:
            writer.writerow(header)
        writer.writerows(rows)


# Re-exports from centralized io module for backward compatibility
# ⚠️ DEPRECATED: These functions will be removed in v0.3.0
# Please migrate to transcriptx.io module (see migration guide above)
import warnings

def _deprecation_warning(func_name: str):
    """
    Issue deprecation warning for functions being moved to transcriptx.io.
    
    This function is called for all deprecated re-exported functions to warn
    developers about the upcoming removal in v0.3.0.
    """
    warnings.warn(
        f"transcriptx.io_utils.{func_name} is deprecated and will be removed in v0.3.0. "
        f"Use transcriptx.io.{func_name} instead.",
        DeprecationWarning,
        stacklevel=3
    )

# Re-export key functions with deprecation warnings
def load_segments(path: str) -> list[dict[str, Any]]:
    """DEPRECATED: Use transcriptx.io.load_segments instead"""
    _deprecation_warning("load_segments")
    from transcriptx.io import load_segments as _load_segments
    return _load_segments(path)

def load_transcript(path: str) -> Any:
    """DEPRECATED: Use transcriptx.io.load_transcript instead"""
    _deprecation_warning("load_transcript")
    from transcriptx.io import load_transcript as _load_transcript
    return _load_transcript(path)

def load_transcript_data(transcript_path: str) -> tuple[list[dict[str, Any]], str, str, dict[str, str]]:
    """DEPRECATED: Use transcriptx.io.load_transcript_data instead"""
    _deprecation_warning("load_transcript_data")
    from transcriptx.io import load_transcript_data as _load_transcript_data
    return _load_transcript_data(transcript_path)

def load_speaker_map(transcript_path: str) -> dict[str, str]:
    """DEPRECATED: Use transcriptx.io.load_speaker_map instead"""
    _deprecation_warning("load_speaker_map")
    from transcriptx.io import load_speaker_map as _load_speaker_map
    return _load_speaker_map(transcript_path)

def save_json(data: dict, path: str):
    """DEPRECATED: Use transcriptx.io.save_json instead"""
    _deprecation_warning("save_json")
    from transcriptx.io import save_json as _save_json
    return _save_json(data, path)

def save_csv(rows: list[list], path: str, header: list[str] | None = None) -> None:
    """DEPRECATED: Use transcriptx.io.save_csv instead"""
    _deprecation_warning("save_csv")
    from transcriptx.io import save_csv as _save_csv
    return _save_csv(rows, path, header)
