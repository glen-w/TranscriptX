"""Speaker eligibility and grouping for per-speaker LLM summaries."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from transcriptx.core.analysis.llm_support.prompts import format_transcript_lines
from transcriptx.core.utils.speaker_extraction import (
    get_unique_speakers,
    group_segments_by_speaker,
)
from transcriptx.utils.text_utils import is_eligible_named_speaker

__all__ = [
    "is_named_speaker_eligible_for_llm",
    "collect_named_speaker_groups_for_llm",
    "canonical_speaker_key",
    "speaker_limit_for_cell_cap",
]


def canonical_speaker_key(
    display_name: str,
    grouping_key: Any,
    runtime_flags: Dict[str, Any],
) -> str:
    """Return the eligibility/alias key used as canonical speaker_key everywhere."""
    speaker_key = str(grouping_key)
    aliases = runtime_flags.get("speaker_key_aliases", {})
    if isinstance(aliases, dict):
        return str(aliases.get(display_name, speaker_key))
    return speaker_key


def _speaker_key_for_eligibility(
    display_name: str,
    grouping_key: Any,
    runtime_flags: Dict[str, Any],
) -> str:
    return canonical_speaker_key(display_name, grouping_key, runtime_flags)


def is_named_speaker_eligible_for_llm(
    display_name: str,
    grouping_key: Any,
    *,
    runtime_flags: Dict[str, Any],
) -> bool:
    """Return True when a speaker should receive an llm_speaker_summary artifact."""
    if not display_name:
        return False
    ignored_ids = runtime_flags.get("ignored_speaker_ids")
    if not isinstance(ignored_ids, set):
        ignored_ids = set()
    speaker_key = _speaker_key_for_eligibility(
        display_name,
        grouping_key,
        runtime_flags,
    )
    named_keys = runtime_flags.get("named_speaker_keys")
    if isinstance(named_keys, set):
        return speaker_key in named_keys or str(grouping_key) in named_keys
    return is_eligible_named_speaker(
        display_name=display_name,
        speaker_id=speaker_key,
        ignored_ids=ignored_ids,
    )


def speaker_limit_for_cell_cap(
    *,
    max_eligible_speakers: int,
    max_speaker_question_cells: int,
    per_speaker_question_count: int,
) -> int:
    """Exact cell-cap formula from the custom QA v2 plan."""
    if per_speaker_question_count <= 0:
        return 0
    by_cells = max_speaker_question_cells // per_speaker_question_count
    return min(max_eligible_speakers, by_cells)


def collect_named_speaker_groups_for_llm(
    segments: List[Dict[str, Any]],
    *,
    runtime_flags: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Return eligible named speakers with non-empty transcript lines.

    Each entry contains ``display_name``, ``speaker_key`` (canonical eligibility
    key), ``grouping_key`` (lexicographically smallest representative),
    ``grouping_keys`` (all source keys after alias-collision merge), and
    ``segments`` (chronological utterances).
    """
    grouped = group_segments_by_speaker(segments)
    display_map = get_unique_speakers(segments)

    # Bucket by canonical speaker_key after per-key eligibility.
    buckets: Dict[str, Dict[str, Any]] = {}
    for grouping_key, speaker_segments in grouped.items():
        display_name = display_map.get(grouping_key)
        if not display_name:
            continue
        if not is_named_speaker_eligible_for_llm(
            display_name,
            grouping_key,
            runtime_flags=runtime_flags,
        ):
            continue
        if not format_transcript_lines(speaker_segments):
            continue
        speaker_key = canonical_speaker_key(display_name, grouping_key, runtime_flags)
        bucket = buckets.get(speaker_key)
        if bucket is None:
            buckets[speaker_key] = {
                "speaker_key": speaker_key,
                "display_names": [display_name],
                "grouping_keys": [grouping_key],
                "segments": list(speaker_segments),
            }
        else:
            bucket["display_names"].append(display_name)
            bucket["grouping_keys"].append(grouping_key)
            bucket["segments"].extend(speaker_segments)

    entries: List[Dict[str, Any]] = []
    for speaker_key, bucket in buckets.items():
        grouping_keys: Tuple[Any, ...] = tuple(
            sorted(bucket["grouping_keys"], key=lambda k: str(k))
        )
        display_name = min(bucket["display_names"], key=lambda n: (n.casefold(), n))
        # Chronological merge: sort by start time when present, else preserve order.
        segs = list(bucket["segments"])
        segs.sort(
            key=lambda s: (
                float(s["start"]) if isinstance(s.get("start"), (int, float)) else 0.0,
                str(s.get("text") or ""),
            )
        )
        entries.append(
            {
                "display_name": display_name,
                "speaker_key": speaker_key,
                "grouping_key": grouping_keys[0],
                "grouping_keys": grouping_keys,
                "segments": segs,
            }
        )

    entries.sort(
        key=lambda item: (
            str(item["display_name"]).casefold(),
            str(item["speaker_key"]),
        )
    )
    return entries
