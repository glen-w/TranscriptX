"""
Shared speaker identification utilities for CLI workflows.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import questionary
from rich import print

from transcriptx.io import load_segments
from transcriptx.io.speaker_mapping import build_speaker_map
from transcriptx.core.utils.file_rename import rename_transcript_after_speaker_mapping
from transcriptx.cli.processing_state import get_current_transcript_path_from_state
from transcriptx.database.services.transcript_store_policy import (
    store_transcript_after_speaker_identification,
)
from transcriptx.utils.text_utils import is_named_speaker


class SpeakerGateDecision(str, Enum):
    """Decision from speaker identification gate check."""

    IDENTIFY = "identify"
    PROCEED = "proceed"
    SKIP = "skip"


@dataclass
class SpeakerIdStatus:
    """Status of speaker identification for a transcript."""

    is_ok: bool
    is_complete: bool
    named_count: int
    total_count: int
    segment_named_count: int
    segment_total_count: int
    missing_ids: List[str]

    def __post_init__(self) -> None:
        """Validate consistency of status fields (tolerant of filtered/corrupted IDs)."""
        assert 0 <= self.named_count <= self.total_count
        assert 0 <= self.segment_named_count <= self.segment_total_count
        # Missing IDs should be unique and not exceed the gap (tolerant of filtered IDs)
        assert len(set(self.missing_ids)) == len(self.missing_ids), "missing_ids must be unique"
        assert (
            self.named_count + len(self.missing_ids) <= self.total_count
        ), "named + missing should not exceed total"
        # is_complete: all named and at least one speaker exists
        assert self.is_complete == (
            self.named_count == self.total_count and self.total_count > 0
        )
        # is_ok: at least one named OR no speakers at all (treat as single-speaker)
        assert self.is_ok == (self.named_count > 0 or self.total_count == 0)


def _normalize_speaker_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip()
        return normalized if normalized else None
    return str(value)


def _load_transcript_json(transcript_path: Path | str) -> Dict[str, Any]:
    path = Path(transcript_path)
    # Try to resolve path if file doesn't exist (handles renamed files)
    resolved_path = path
    if not path.exists():
        try:
            from transcriptx.core.utils._path_resolution import resolve_file_path
            resolved_path = Path(resolve_file_path(str(transcript_path), file_type="transcript"))
        except FileNotFoundError:
            # If resolution fails, continue with original path to get proper error
            pass
    
    try:
        with resolved_path.open("r") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _resolve_speaker_map_label(
    speaker_id: str,
    speaker_map: Dict[str, str],
) -> Optional[str]:
    if not speaker_map:
        return None
    if speaker_id in speaker_map:
        return speaker_map[speaker_id]
    string_id = str(speaker_id)
    return speaker_map.get(string_id)


def _segment_speaker_id(seg: Dict[str, Any]) -> Optional[str]:
    raw_id = (
        seg.get("speaker_id")
        if seg.get("speaker_id") is not None
        else seg.get("speaker_db_id")
        if seg.get("speaker_db_id") is not None
        else seg.get("speaker")
    )
    return _normalize_speaker_id(raw_id)


def _segment_speaker_label(seg: Dict[str, Any], speaker_map: Dict[str, str]) -> Optional[str]:
    """
    Best-effort label resolution for a single segment.

    Order:
    - Use speaker_map if we can resolve an ID
    - Fall back to common per-segment label fields
    - Fall back to the speaker_id itself
    """
    speaker_id = _segment_speaker_id(seg)
    if speaker_id:
        mapped = _resolve_speaker_map_label(speaker_id, speaker_map)
        if mapped and str(mapped).strip():
            return str(mapped).strip()

    for key in ("speaker_display_name", "speaker_name", "display_name", "speaker"):
        value = seg.get(key)
        if value is None:
            continue
        label = str(value).strip()
        if label:
            return label

    return speaker_id


def _collect_segment_labels(
    segments: Iterable[Dict[str, Any]],
    canonical_id_map: Dict[str, List[str]],
) -> None:
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        raw_id = (
            seg.get("speaker_id")
            if seg.get("speaker_id") is not None
            else seg.get("speaker_db_id")
            if seg.get("speaker_db_id") is not None
            else seg.get("speaker")
        )
        speaker_id = _normalize_speaker_id(raw_id)
        if not speaker_id:
            continue
        canonical_id_map.setdefault(speaker_id, [])
        for key in ("speaker_display_name", "speaker_name", "display_name", "speaker"):
            value = seg.get(key)
            if value is None:
                continue
            label = str(value).strip()
            if label:
                canonical_id_map[speaker_id].append(label)


def has_named_speakers(transcript_path: Path | str) -> bool:
    """Check if transcript has at least one named speaker (public API)."""
    status = check_speaker_identification_status(transcript_path)
    return status.is_ok


def check_speaker_identification_status(
    transcript_path: Path | str,
    allow_generic_names: bool = False,
) -> SpeakerIdStatus:
    """
    Get detailed status of speaker identification.

    Args:
        transcript_path: Path to transcript file
        allow_generic_names: If True, allow "Unknown", "Speaker A" etc. as named

    Returns:
        SpeakerIdStatus with counts and missing IDs

    Note:
        - Computes missing_ids from actual segments, not just speaker_map
        - Uses is_named_speaker() as the single authority for what counts as "named"
        - Handles "no speakers" case: total_count=0, is_ok=True, is_complete=False
    """
    segments = load_segments(str(transcript_path))
    transcript_data = _load_transcript_json(transcript_path)
    speaker_map = transcript_data.get("speaker_map", {})
    if not isinstance(speaker_map, dict):
        speaker_map = {}

    segment_total_count = 0
    segment_named_count = 0
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        segment_total_count += 1
        label = _segment_speaker_label(seg, speaker_map)
        if not label:
            continue
        if allow_generic_names:
            if label.strip():
                segment_named_count += 1
        else:
            if is_named_speaker(label):
                segment_named_count += 1

    canonical_ids: Dict[str, List[str]] = defaultdict(list)
    _collect_segment_labels(segments, canonical_ids)

    speaker_ids = sorted(canonical_ids.keys())
    total_count = len(speaker_ids)

    if total_count == 0:
        return SpeakerIdStatus(
            is_ok=True,
            is_complete=False,
            named_count=0,
            total_count=0,
            segment_named_count=segment_named_count,
            segment_total_count=segment_total_count,
            missing_ids=[],
        )

    def is_label_named(label: str) -> bool:
        if allow_generic_names:
            return bool(label.strip())
        return is_named_speaker(label)

    named_ids: List[str] = []
    missing_ids: List[str] = []

    for speaker_id in speaker_ids:
        label = _resolve_speaker_map_label(speaker_id, speaker_map)
        if not label:
            candidates = canonical_ids.get(speaker_id, [])
            if candidates:
                label = Counter(candidates).most_common(1)[0][0]
        if not label:
            label = speaker_id
        if is_label_named(label):
            named_ids.append(speaker_id)
        else:
            missing_ids.append(speaker_id)

    named_count = len(named_ids)
    is_ok = named_count > 0
    is_complete = named_count == total_count and total_count > 0

    return SpeakerIdStatus(
        is_ok=is_ok,
        is_complete=is_complete,
        named_count=named_count,
        total_count=total_count,
        segment_named_count=segment_named_count,
        segment_total_count=segment_total_count,
        missing_ids=missing_ids,
    )


def check_speaker_gate(
    transcript_path: str,
    transcript_name: Optional[str] = None,
    force_non_interactive: bool = False,
) -> tuple[SpeakerGateDecision, SpeakerIdStatus]:
    """
    Check speaker identification and prompt user if needed.

    Returns:
        (decision, status) - decision and status for caller to use
    """
    status = check_speaker_identification_status(transcript_path)

    # Proceed silently only if complete OR no speakers found (treat as single-speaker)
    if status.is_complete or status.total_count == 0:
        return (SpeakerGateDecision.PROCEED, status)

    if force_non_interactive:
        return (SpeakerGateDecision.PROCEED, status)

    name = transcript_name or Path(transcript_path).name
    if status.named_count > 0:
        msg = (
            f"Partial speaker identification for {name} "
            f"({status.named_count}/{status.total_count} identified)."
        )
    else:
        msg = f"Speakers not yet identified for {name} ({status.total_count} speakers found)."

    choice = questionary.select(
        f"{msg} What would you like to do?",
        choices=[
            questionary.Choice(
                "✅ Identify speakers first (recommended)",
                value=SpeakerGateDecision.IDENTIFY,
            ),
            questionary.Choice(
                "⚠️ Proceed with analysis anyway",
                value=SpeakerGateDecision.PROCEED,
            ),
            questionary.Choice(
                "⏭️ Skip analysis",
                value=SpeakerGateDecision.SKIP,
            ),
        ],
        default=SpeakerGateDecision.IDENTIFY,
    ).ask()

    if not choice:
        return (SpeakerGateDecision.SKIP, status)

    decision = choice

    if decision == SpeakerGateDecision.PROCEED:
        if status.named_count == 0:
            print(
                "[yellow]⚠️ Warning: Unidentified speakers will be excluded from most "
                "analysis outputs (word clouds, sentiment, emotion, etc.).[/yellow]"
            )
        else:
            print(
                f"[yellow]⚠️ Warning: {status.total_count - status.named_count} "
                "unidentified speaker(s) will be excluded from most analysis outputs.[/yellow]"
            )

    return (decision, status)


def check_batch_speaker_gate(
    transcript_paths: List[str],
    force_non_interactive: bool = False,
) -> tuple[SpeakerGateDecision, List[str], List[str], dict[str, SpeakerIdStatus]]:
    """
    Check speaker identification for multiple transcripts.

    Returns:
        (decision, needs_identification, already_identified, statuses_dict)
    """
    needs_identification: List[str] = []
    already_identified: List[str] = []
    statuses: dict[str, SpeakerIdStatus] = {}

    for path in transcript_paths:
        status = check_speaker_identification_status(path)
        statuses[path] = status
        if status.is_complete or status.total_count == 0:
            already_identified.append(path)
        else:
            needs_identification.append(path)

    if not needs_identification:
        return (SpeakerGateDecision.PROCEED, needs_identification, already_identified, statuses)

    if force_non_interactive:
        return (SpeakerGateDecision.PROCEED, needs_identification, already_identified, statuses)

    print("\n[bold]Speaker Identification Status:[/bold]")
    print(f"  ✅ Already identified: {len(already_identified)}")
    print(f"  ⚠️  Need identification: {len(needs_identification)}")

    total_speakers = sum(statuses[path].total_count for path in needs_identification)
    total_named_speakers = sum(statuses[path].named_count for path in needs_identification)
    total_missing_speakers = max(0, total_speakers - total_named_speakers)

    total_segments = sum(statuses[path].segment_total_count for path in needs_identification)
    total_named_segments = sum(statuses[path].segment_named_count for path in needs_identification)
    total_missing_segments = max(0, total_segments - total_named_segments)

    choice = questionary.select(
        f"{len(needs_identification)} transcript(s) need speaker identification "
        f"(speakers: {total_named_speakers}/{total_speakers} identified, "
        f"{total_missing_speakers} missing; "
        f"segments: {total_named_segments}/{total_segments} identified, "
        f"{total_missing_segments} missing). What would you like to do?",
        choices=[
            questionary.Choice(
                "✅ Identify missing speakers first (recommended)",
                value=SpeakerGateDecision.IDENTIFY,
            ),
            questionary.Choice(
                "⚠️ Proceed with analysis anyway",
                value=SpeakerGateDecision.PROCEED,
            ),
            questionary.Choice(
                "⏭️ Skip analysis",
                value=SpeakerGateDecision.SKIP,
            ),
        ],
        default=SpeakerGateDecision.IDENTIFY,
    ).ask()

    if not choice:
        return (SpeakerGateDecision.SKIP, needs_identification, already_identified, statuses)

    decision = choice

    if decision == SpeakerGateDecision.PROCEED:
        print(
            "[yellow]⚠️ Warning: Unidentified speakers will be excluded from most "
            "analysis outputs (word clouds, sentiment, emotion, etc.).[/yellow]"
        )
        print(
            f"[yellow]   This may lead to sparse or empty per-speaker outputs for "
            f"{len(needs_identification)} transcript(s).[/yellow]"
        )

    return (decision, needs_identification, already_identified, statuses)


def run_speaker_identification_for_transcript(
    transcript_path: str,
    batch_mode: bool = False,
) -> tuple[bool, str]:
    """
    Run speaker identification for a specific transcript and return updated path.

    Returns:
        (success, updated_path)
    """
    path = Path(transcript_path)
    segments = load_segments(str(path))
    speaker_map = build_speaker_map(
        segments,
        speaker_map_path=None,
        transcript_path=str(path),
        batch_mode=batch_mode,
        auto_generate=False,
        persist_speaker_records=False,
    )
    if not speaker_map:
        return (False, str(path))

    rename_transcript_after_speaker_mapping(str(path))
    updated_path = get_current_transcript_path_from_state(str(path)) or str(path)
    if Path(updated_path).exists():
        store_transcript_after_speaker_identification(updated_path)
    return (True, updated_path)
