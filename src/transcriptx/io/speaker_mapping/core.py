"""Speaker mapping module."""

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from colorama import Fore, Style, init
from rich.console import Console

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils._path_resolution import resolve_file_path
from transcriptx.utils.text_utils import is_named_speaker
from transcriptx.io.speaker_map_resolver import SpeakerMapResolver

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


from .utils import (
    SegmentRef,
    _extract_segment_times,
    _is_test_environment,
    compute_speaker_stats_from_segments,
)
from ._types import GO_BACK_SENTINEL, EXIT_SENTINEL, SpeakerChoice


def _select_name_with_playback(speaker_id, segments, existing_name, audio_path):
    """Delegate to the interactive terminal speaker-mapping implementation."""
    try:
        from .interactive import _select_name_with_playback as _impl  # noqa: PLC0415

        return _impl(
            speaker_id=speaker_id,
            segments=segments,
            existing_name=existing_name,
            audio_path=audio_path,
        )
    except ImportError:
        raise RuntimeError(
            "Interactive terminal speaker mapping is not available in web-only mode. "
            "Use batch_mode=True or the web interface for speaker identification."
        )


def _apply_speaker_map_to_data(
    data: Dict[str, Any],
    speaker_map: Dict[str, str],
    *,
    speaker_id_to_db_id: Optional[Dict[str, int]] = None,
    ignored_speakers: Optional[List[str]] = None,
    rewrite_segment_speakers: bool = True,
    speaker_map_source: Optional[Dict[str, Any]] = None,
    method: str = "interactive",
) -> None:
    """Mutate a transcript-shaped dict in memory only."""
    segments = data.get("segments", [])
    if rewrite_segment_speakers and isinstance(segments, list):
        for seg in segments:
            speaker_id = seg.get("speaker")
            if speaker_id is None:
                continue
            if speaker_id in speaker_map:
                seg["speaker"] = speaker_map[speaker_id]
            if speaker_id_to_db_id and speaker_id in speaker_id_to_db_id:
                seg["speaker_db_id"] = speaker_id_to_db_id[speaker_id]


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
                "❌ No speaker information found in transcript. All segments have speaker: None or missing speaker field.",
                style="red",
            )
            console.print(
                "   This transcript may not have been diarized. Please run speaker diarization first.",
                style="yellow",
            )
        else:
            console.print(
                "❌ No speakers found in transcript. Speaker map will not be created.",
                style="red",
            )
        return {}

    # Sidecar JSON stores display names; no separate speaker record store.

    # Auto-generate speaker names in batch mode, test mode, or when auto_generate is True
    if batch_mode or auto_generate or _is_test_environment():
        new_map = {}
        for i, speaker_id in enumerate(speaker_ids):
            # Use existing name if available, otherwise generate default name
            if existing_map and speaker_id in existing_map:
                new_map[speaker_id] = existing_map[speaker_id]
            else:
                new_map[speaker_id] = f"Speaker {i + 1}"

        if transcript_path and new_map:
            from transcriptx.services.speaker_studio import SpeakerMappingService

            SpeakerMappingService().bulk_update(
                transcript_path, new_map, [], method="batch"
            )
            logger.debug(f"Updated sidecar with speaker names: {transcript_path}")

        return new_map

    resolver = SpeakerMapResolver()
    speaker_map = existing_map or {}
    if transcript_path and not speaker_map:
        loaded_state = resolver.load_mapping(transcript_path)
        if loaded_state.speaker_map:
            speaker_map = loaded_state.speaker_map
            existing_map = speaker_map
    new_map = {}
    existing_ignored = (
        resolver.load_mapping(transcript_path).ignored_speakers
        if transcript_path
        else []
    )
    ignored_speakers = set(existing_ignored)
    new_ignored: list[str] = []

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

        # Skip speakers that don't need review in "unidentified only" mode
        if review_mode == "unidentified only":
            if speaker_id in ignored_speakers:
                i += 1
                continue
            display_label = str(speaker_map.get(speaker_id) or speaker_id)
            if is_named_speaker(display_label):
                i += 1
                continue

        lines = speaker_to_lines[speaker_id]

        # Handle new speaker mapping (no existing map)
        if not speaker_map:
            total = len(lines)
            console.print(
                f"{color}\n📄 Speaker {speaker_id} — {total} lines (showing 10 at a time, press 'm' for more, 't' to toggle sort):{Style.RESET_ALL}"
            )
            choice = _select_name_with_playback(
                speaker_id=str(speaker_id),
                segments=lines,
                existing_name=None,
                audio_path=audio_path,
            )
            # Handle "exit" request
            if choice == EXIT_SENTINEL:
                console.print(
                    "[yellow]Exiting speaker mapping. Returning to menu...[/yellow]"
                )
                return None
            # Handle "go back" request
            if choice == GO_BACK_SENTINEL:
                if i > 0:
                    # Find the previous speaker that needs review
                    i -= 1
                    # Continue to previous speaker, but need to skip backwards through any skipped speakers
                    while i >= 0:
                        prev_speaker_id = speaker_ids[i]
                        if review_mode == "unidentified only":
                            if prev_speaker_id in ignored_speakers:
                                i -= 1
                                continue
                            prev_label = str(
                                speaker_map.get(prev_speaker_id) or prev_speaker_id
                            )
                            if is_named_speaker(prev_label):
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
            if isinstance(choice, SpeakerChoice) and choice.action == "ignore":
                new_ignored.append(str(speaker_id))
                ignored_speakers.add(speaker_id)
                i += 1
            elif (
                isinstance(choice, SpeakerChoice)
                and choice.action == "name"
                and choice.value
            ):
                display_name = choice.value.strip()
                new_map[speaker_id] = display_name
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
            choice = _select_name_with_playback(
                speaker_id=str(speaker_id),
                segments=lines,
                existing_name=existing_name,
                audio_path=audio_path,
            )
            # Handle "exit" request
            if choice == EXIT_SENTINEL:
                console.print(
                    "[yellow]Exiting speaker mapping. Returning to menu...[/yellow]"
                )
                return None
            # Handle "go back" request
            if choice == GO_BACK_SENTINEL:
                if i > 0:
                    # Find the previous speaker that needs review
                    i -= 1
                    # Continue to previous speaker, but need to skip backwards through any skipped speakers
                    while i >= 0:
                        prev_speaker_id = speaker_ids[i]
                        if review_mode == "unidentified only":
                            if prev_speaker_id in ignored_speakers:
                                i -= 1
                                continue
                            prev_label = str(
                                speaker_map.get(prev_speaker_id) or prev_speaker_id
                            )
                            if is_named_speaker(prev_label):
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
            if isinstance(choice, SpeakerChoice) and choice.action == "ignore":
                new_ignored.append(str(speaker_id))
                ignored_speakers.add(speaker_id)
                i += 1
            elif isinstance(choice, SpeakerChoice) and choice.action == "skip":
                new_map[speaker_id] = existing_name or speaker_id
                i += 1
            elif (
                isinstance(choice, SpeakerChoice)
                and choice.action == "name"
                and choice.value
            ):
                display_name = choice.value.strip()
                new_map[speaker_id] = display_name
                console.print(
                    f"[green]✅ {speaker_id} → {display_name} (saved)[/green]"
                )
                i += 1
            else:
                new_map[speaker_id] = existing_name or speaker_id
                i += 1

    # Merge existing map with newly identified so we preserve already-named speakers
    final_map = {**(existing_map or {}), **new_map}

    # Speaker Mapping Summary (before persist): use true final_map so UI matches persisted data
    ignored_set = set(dict.fromkeys(existing_ignored + new_ignored))
    stats = compute_speaker_stats_from_segments(segments)
    mapped_ids = [
        sid
        for sid in speaker_ids
        if sid not in ignored_set and final_map.get(sid, sid) != sid
    ]
    unmapped_ids = [
        sid
        for sid in speaker_ids
        if sid not in ignored_set and final_map.get(sid, sid) == sid
    ]

    console.print("\n[bold]Speaker Mapping Summary[/bold]")
    console.print("-" * 50)
    for sid in sorted(mapped_ids):
        s = stats.get(sid, {})
        name = final_map.get(sid, sid)
        count = s.get("segment_count", 0)
        dur = s.get("total_duration", 0.0)
        pct = s.get("percent", 0.0)
        if dur > 0:
            console.print(
                f"  [green]{sid}[/green] → {name}: {count} segments, "
                f"{dur:.1f}s ({pct:.1f}%)"
            )
        else:
            console.print(
                f"  [green]{sid}[/green] → {name}: {count} segments ({pct:.1f}%)"
            )
    if unmapped_ids:
        console.print("[dim]Unmapped:[/dim]")
        for sid in sorted(unmapped_ids):
            s = stats.get(sid, {})
            count = s.get("segment_count", 0)
            dur = s.get("total_duration", 0.0)
            pct = s.get("percent", 0.0)
            if dur > 0:
                console.print(
                    f"  [yellow]{sid}[/yellow]: {count} segments, "
                    f"{dur:.1f}s ({pct:.1f}%)"
                )
            else:
                console.print(
                    f"  [yellow]{sid}[/yellow]: {count} segments ({pct:.1f}%)"
                )
    console.print(
        "\n[dim]Note: Unmapped speakers will be excluded from most per-speaker "
        "analyses (sentiment, emotion, word clouds, stats-by-speaker). "
        "They may still appear in raw transcript outputs and NER/global "
        "outputs if configured.[/dim]\n"
    )

    # Persist sidecar if transcript_path is provided and we have a map
    if transcript_path and final_map:
        from transcriptx.services.speaker_studio import SpeakerMappingService

        SpeakerMappingService().bulk_update(
            transcript_path,
            final_map,
            list(ignored_set),
            method="interactive",
        )
        logger.debug(f"Updated sidecar with speaker names: {transcript_path}")
        console.print(f"[dim]Persistence path: {transcript_path}[/dim]")
        console.print(
            f"[green]✔ Speaker mapping saved to sidecar for: {transcript_path}[/green]"
        )
        console.print(
            "[dim]Future runs will reuse this mapping unless overridden.[/dim]"
        )
        console.print(
            "[dim]Mapping is stored in the sidecar file alongside the transcript.[/dim]"
        )

    return final_map
