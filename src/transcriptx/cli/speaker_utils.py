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
from transcriptx.io.transcript_loader import (
    extract_ignored_speakers_from_transcript,
    extract_speaker_map_from_transcript,
)
from transcriptx.core.utils.config import get_config
from transcriptx.core.pipeline.target_resolver import resolve_transcript_paths
from transcriptx.core.utils.file_rename import rename_transcript_after_speaker_mapping
from transcriptx.core.utils.logger import log_info
from transcriptx.cli.processing_state import get_current_transcript_path_from_state
from transcriptx.database.services.transcript_store_policy import (
    store_transcript_after_speaker_identification,
)
from transcriptx.utils.text_utils import is_named_speaker

_MAX_SNIPPET_LENGTH = 80
_MAX_BATCH_EXEMPLAR_SPEAKERS = 6
_MAX_BATCH_EXEMPLAR_SNIPPETS = 2


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
    ignored_count: int
    named_count: int
    resolved_count: int
    total_count: int
    segment_named_count: int
    segment_total_count: int
    missing_ids: List[str]

    def __post_init__(self) -> None:
        """Validate consistency of status fields (tolerant of filtered/corrupted IDs)."""
        assert self.resolved_count == (
            self.named_count + self.ignored_count
        ), "resolved_count must equal named + ignored"
        assert 0 <= self.named_count <= self.total_count
        assert 0 <= self.ignored_count <= self.total_count
        assert 0 <= self.segment_named_count <= self.segment_total_count
        # Missing IDs should be unique and not exceed the gap (tolerant of filtered IDs)
        assert len(set(self.missing_ids)) == len(self.missing_ids), "missing_ids must be unique"
        assert (
            self.resolved_count + len(self.missing_ids) == self.total_count
        ), "resolved + missing must equal total"
        # is_complete: all resolved OR no speakers
        assert self.is_complete == (
            self.total_count == 0 or self.resolved_count == self.total_count
        )
        # is_ok: gate decision mirrors completion
        assert self.is_ok == self.is_complete


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


def _collapse_whitespace(text: str) -> str:
    return " ".join(text.split()).strip()


def _truncate_snippet(text: str, max_length: int = _MAX_SNIPPET_LENGTH) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _tokenize_lightweight(text: str) -> List[str]:
    tokens: List[str] = []
    for raw in text.split():
        stripped = raw.strip(".,!?;:\"'()[]{}<>")
        stripped = stripped.strip("-_")
        if not stripped:
            continue
        tokens.append(stripped)
    return tokens


def _uniqueness_score(text: str) -> float:
    tokens = _tokenize_lightweight(text)
    if not tokens:
        return 0.0
    return float(len(set(tokens)) + 0.1 * len(tokens))


def get_unidentified_speaker_exemplars(
    transcript_path: str,
    missing_ids: List[str],
    exemplar_count: int = 2,
    *,
    segments: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, List[str]]:
    """
    Return short, distinctive snippet exemplars for unidentified speakers.

    - Uses only simple token splits (no NLP deps).
    - Dedupe identical snippet texts per speaker.
    - Handles empty/punctuation-only text by skipping.
    """
    if exemplar_count <= 0 or not missing_ids:
        return {}

    missing_set = set(missing_ids)
    if segments is None:
        segments = load_segments(str(transcript_path))

    candidates: Dict[str, List[tuple[float, str]]] = defaultdict(list)
    seen_texts: Dict[str, set[str]] = defaultdict(set)

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        speaker_id = _segment_speaker_id(seg)
        if not speaker_id or speaker_id not in missing_set:
            continue
        text = _collapse_whitespace(str(seg.get("text", "")))
        if not text:
            continue
        if text in seen_texts[speaker_id]:
            continue
        score = _uniqueness_score(text)
        if score <= 0.0:
            continue
        seen_texts[speaker_id].add(text)
        candidates[speaker_id].append((score, text))

    exemplars: Dict[str, List[str]] = {}
    for speaker_id, items in candidates.items():
        items.sort(key=lambda item: (item[0], len(item[1])), reverse=True)
        snippets: List[str] = []
        for _, text in items:
            snippet = _truncate_snippet(text)
            if snippet in snippets:
                continue
            snippets.append(snippet)
            if len(snippets) >= exemplar_count:
                break
        if snippets:
            exemplars[speaker_id] = snippets

    return exemplars


def _speaker_gate_choice_specs(
    mode: str, *, batch: bool
) -> List[tuple[str, SpeakerGateDecision]]:
    identify_label = (
        "✅ Identify missing speakers first (recommended)"
        if batch
        else "✅ Identify speakers first (recommended)"
    )
    choices: List[tuple[str, SpeakerGateDecision]] = [
        (identify_label, SpeakerGateDecision.IDENTIFY),
    ]
    if mode != "enforce":
        choices.append(("⚠️ Proceed with analysis anyway", SpeakerGateDecision.PROCEED))
    choices.append(("⏭️ Skip analysis", SpeakerGateDecision.SKIP))
    return choices


def _within_speaker_gate_threshold_counts(
    segment_total_count: int,
    segment_named_count: int,
    config: Any,
) -> bool:
    if segment_total_count == 0:
        return True
    missing_segments = max(0, segment_total_count - segment_named_count)
    if config.threshold_type == "percentage":
        return (missing_segments / segment_total_count) * 100 <= config.threshold_value
    threshold_value = int(config.threshold_value)
    return missing_segments <= threshold_value


def _within_speaker_gate_threshold(status: SpeakerIdStatus, config: Any) -> bool:
    """
    Threshold is applied to unidentified segment count (segment_total_count - segment_named_count),
    not to the number of unidentified speakers.
    """
    return _within_speaker_gate_threshold_counts(
        status.segment_total_count,
        status.segment_named_count,
        config,
    )


def _log_speaker_gate_skip(
    segment_total_count: int,
    segment_named_count: int,
    config: Any,
) -> None:
    missing_segments = max(0, segment_total_count - segment_named_count)
    if config.threshold_type == "percentage":
        pct = 0.0 if segment_total_count == 0 else (missing_segments / segment_total_count) * 100
        message = (
            "Speaker gate: within threshold "
            f"({missing_segments}/{segment_total_count} segments, "
            f"{pct:.1f}% <= {config.threshold_value:.1f}%); proceeding without prompt."
        )
    else:
        threshold_value = int(config.threshold_value)
        message = (
            "Speaker gate: within threshold "
            f"({missing_segments}/{segment_total_count} segments, "
            f"absolute <= {threshold_value}); proceeding without prompt."
        )
    log_info("SPEAKER_GATE", message)


def _print_exemplars(
    exemplars: Dict[str, List[str]],
    *,
    header: Optional[str] = None,
    max_speakers: Optional[int] = None,
    max_snippets: Optional[int] = None,
) -> None:
    if not exemplars:
        return
    if header:
        print(header)
    speaker_ids = list(exemplars.keys())
    if max_speakers is not None:
        speaker_ids = speaker_ids[:max_speakers]
    for speaker_id in speaker_ids:
        snippets = exemplars.get(speaker_id, [])
        if max_snippets is not None:
            snippets = snippets[:max_snippets]
        if not snippets:
            continue
        joined = " ".join(f"\"{snippet}\"" for snippet in snippets)
        print(f"  {speaker_id}: {joined}")

def has_named_speakers(transcript_path: Path | str) -> bool:
    """Check if transcript has at least one named speaker (public API)."""
    status = check_speaker_identification_status(transcript_path)
    return status.named_count > 0


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
        - Handles "no speakers" case: total_count=0, is_ok=True, is_complete=True
    """
    segments = load_segments(str(transcript_path))
    transcript_data = _load_transcript_json(transcript_path)
    speaker_map = transcript_data.get("speaker_map", {})
    if not isinstance(speaker_map, dict):
        speaker_map = {}
    ignored_ids = set(extract_ignored_speakers_from_transcript(transcript_path))

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
            is_complete=True,
            ignored_count=0,
            named_count=0,
            resolved_count=0,
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
        if speaker_id in ignored_ids:
            continue
        if is_label_named(label):
            named_ids.append(speaker_id)
        else:
            missing_ids.append(speaker_id)

    named_count = len(named_ids)
    ignored_count = sum(1 for speaker_id in speaker_ids if speaker_id in ignored_ids)
    resolved_count = named_count + ignored_count
    is_complete = total_count == 0 or resolved_count == total_count
    is_ok = is_complete

    return SpeakerIdStatus(
        is_ok=is_ok,
        is_complete=is_complete,
        ignored_count=ignored_count,
        named_count=named_count,
        resolved_count=resolved_count,
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
    config = get_config().workflow.speaker_gate

    # Proceed silently only if complete OR no speakers found (treat as single-speaker)
    if status.is_complete or status.total_count == 0:
        return (SpeakerGateDecision.PROCEED, status)

    if force_non_interactive:
        if config.mode == "enforce":
            return (SpeakerGateDecision.SKIP, status)
        return (SpeakerGateDecision.PROCEED, status)

    if config.mode == "ignore" and _within_speaker_gate_threshold(status, config):
        _log_speaker_gate_skip(
            status.segment_total_count,
            status.segment_named_count,
            config,
        )
        return (SpeakerGateDecision.PROCEED, status)

    name = transcript_name or Path(transcript_path).name
    if status.named_count > 0:
        msg = (
            f"Partial speaker identification for {name} "
            f"({status.named_count}/{status.total_count} identified)."
        )
    else:
        msg = f"Speakers not yet identified for {name} ({status.total_count} speakers found)."

    if config.exemplar_count > 0 and status.missing_ids:
        exemplars = get_unidentified_speaker_exemplars(
            transcript_path,
            status.missing_ids,
            config.exemplar_count,
        )
        _print_exemplars(exemplars, header="[dim]Unidentified speaker samples:[/dim]")

    choice = questionary.select(
        f"{msg} What would you like to do?",
        choices=[
            questionary.Choice(label, value=decision)
            for label, decision in _speaker_gate_choice_specs(
                config.mode, batch=False
            )
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

    config = get_config().workflow.speaker_gate

    if force_non_interactive:
        if config.mode == "enforce":
            return (SpeakerGateDecision.SKIP, needs_identification, already_identified, statuses)
        return (SpeakerGateDecision.PROCEED, needs_identification, already_identified, statuses)

    if config.mode == "ignore":
        total_segments = sum(
            statuses[path].segment_total_count for path in needs_identification
        )
        total_named_segments = sum(
            statuses[path].segment_named_count for path in needs_identification
        )
        if _within_speaker_gate_threshold_counts(
            total_segments,
            total_named_segments,
            config,
        ):
            _log_speaker_gate_skip(total_segments, total_named_segments, config)
            return (
                SpeakerGateDecision.PROCEED,
                needs_identification,
                already_identified,
                statuses,
            )

    print("\n[bold]Speaker Identification Status:[/bold]")
    print(f"  ✅ Already identified: {len(already_identified)}")
    print(f"  ⚠️  Need identification: {len(needs_identification)}")

    total_speakers = sum(statuses[path].total_count for path in needs_identification)
    total_named_speakers = sum(statuses[path].named_count for path in needs_identification)
    total_missing_speakers = max(0, total_speakers - total_named_speakers)

    total_segments = sum(statuses[path].segment_total_count for path in needs_identification)
    total_named_segments = sum(statuses[path].segment_named_count for path in needs_identification)
    total_missing_segments = max(0, total_segments - total_named_segments)

    if config.exemplar_count > 0:
        for path in needs_identification:
            status = statuses[path]
            if not status.missing_ids:
                continue
            exemplars = get_unidentified_speaker_exemplars(
                path,
                status.missing_ids,
                config.exemplar_count,
            )
            if not exemplars:
                continue
            header = f"[dim]{Path(path).name} - Unidentified speaker samples:[/dim]"
            missing_order = [
                speaker_id for speaker_id in status.missing_ids if speaker_id in exemplars
            ]
            capped_ids = missing_order[:_MAX_BATCH_EXEMPLAR_SPEAKERS]
            capped_exemplars = {speaker_id: exemplars[speaker_id] for speaker_id in capped_ids}
            _print_exemplars(
                capped_exemplars,
                header=header,
                max_speakers=_MAX_BATCH_EXEMPLAR_SPEAKERS,
                max_snippets=_MAX_BATCH_EXEMPLAR_SNIPPETS,
            )

    choice = questionary.select(
        f"{len(needs_identification)} transcript(s) need speaker identification "
        f"(speakers: {total_named_speakers}/{total_speakers} identified, "
        f"{total_missing_speakers} missing; "
        f"segments: {total_named_segments}/{total_segments} identified, "
        f"{total_missing_segments} missing). What would you like to do?",
        choices=[
            questionary.Choice(label, value=decision)
            for label, decision in _speaker_gate_choice_specs(
                config.mode, batch=True
            )
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


def check_group_speaker_preflight(
    member_transcript_ids: List[int],
    force_non_interactive: bool = False,
) -> tuple[SpeakerGateDecision, List[str], List[str], dict[str, SpeakerIdStatus]]:
    """
    Check speaker identification for group members by transcript ID.
    """
    try:
        resolved_paths = [str(path) for path in resolve_transcript_paths(member_transcript_ids)]
    except ValueError as exc:
        print(f"\n[red]❌ {exc}[/red]")
        return (SpeakerGateDecision.SKIP, [], [], {})

    needs_identification: List[str] = []
    already_identified: List[str] = []
    statuses: dict[str, SpeakerIdStatus] = {}

    for path in resolved_paths:
        try:
            status = check_speaker_identification_status(path)
        except Exception as exc:
            print(f"\n[red]❌ Failed to parse transcript: {path} ({exc})[/red]")
            return (SpeakerGateDecision.SKIP, [], [], {})
        statuses[path] = status
        if status.is_complete or status.total_count == 0:
            already_identified.append(path)
        else:
            needs_identification.append(path)

    if not needs_identification:
        return (SpeakerGateDecision.PROCEED, needs_identification, already_identified, statuses)

    if force_non_interactive:
        config = get_config().workflow.speaker_gate
        if config.mode == "enforce":
            return (SpeakerGateDecision.SKIP, needs_identification, already_identified, statuses)
        return (SpeakerGateDecision.PROCEED, needs_identification, already_identified, statuses)

    print("\n[bold]Speaker Identification Status:[/bold]")
    print(f"  ✅ Already identified: {len(already_identified)}")
    print(f"  ⚠️  Need identification: {len(needs_identification)}")

    choices: List[questionary.Choice] = [
        questionary.Choice(
            "🔄 Run speaker mapping for missing now", SpeakerGateDecision.IDENTIFY
        ),
    ]
    if get_config().workflow.speaker_gate.mode != "enforce":
        choices.append(
            questionary.Choice(
                "✅ Continue analysis anyway (unidentified speakers largely ignored in outputs)",
                SpeakerGateDecision.PROCEED,
            )
        )
    choices.append(questionary.Choice("⏭️ Cancel analysis", SpeakerGateDecision.SKIP))

    choice = questionary.select(
        f"{len(needs_identification)} transcript(s) need speaker identification. What would you like to do?",
        choices=choices,
        default=SpeakerGateDecision.IDENTIFY,
    ).ask()
    if not choice:
        return (SpeakerGateDecision.SKIP, needs_identification, already_identified, statuses)
    return (choice, needs_identification, already_identified, statuses)


def run_speaker_identification_for_transcript(
    transcript_path: str,
    batch_mode: bool = False,
    from_gate: bool = False,
) -> tuple[bool, str]:
    """
    Run speaker identification for a specific transcript and return updated path.

    When from_gate is True (invoked from a "speaker ID needed" step), only
    unidentified speakers are shown; already-named speakers are skipped.

    Returns:
        (success, updated_path)
    """
    path = Path(transcript_path)
    segments = load_segments(str(path))
    existing_map = extract_speaker_map_from_transcript(str(path)) if from_gate else None
    speaker_map = build_speaker_map(
        segments,
        speaker_map_path=None,
        review_mode="unidentified only" if from_gate else "all",
        existing_map=existing_map,
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
