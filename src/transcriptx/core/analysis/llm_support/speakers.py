"""Speaker eligibility and grouping for per-speaker LLM summaries."""

from __future__ import annotations

from typing import Any, Dict, List

from transcriptx.core.analysis.llm_support.prompts import format_transcript_lines
from transcriptx.core.utils.speaker_extraction import (
    get_unique_speakers,
    group_segments_by_speaker,
)
from transcriptx.utils.text_utils import is_eligible_named_speaker

__all__ = [
    "is_named_speaker_eligible_for_llm",
    "collect_named_speaker_groups_for_llm",
]


def _speaker_key_for_eligibility(
    display_name: str,
    grouping_key: Any,
    runtime_flags: Dict[str, Any],
) -> str:
    speaker_key = str(grouping_key)
    aliases = runtime_flags.get("speaker_key_aliases", {})
    if isinstance(aliases, dict):
        return str(aliases.get(display_name, speaker_key))
    return speaker_key


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


def collect_named_speaker_groups_for_llm(
    segments: List[Dict[str, Any]],
    *,
    runtime_flags: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Return eligible named speakers with non-empty transcript lines.

    Each entry contains ``display_name``, ``speaker_key``, ``grouping_key``,
    and ``segments`` (chronological utterances for that speaker).
    """
    grouped = group_segments_by_speaker(segments)
    display_map = get_unique_speakers(segments)
    entries: List[Dict[str, Any]] = []

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
        entries.append(
            {
                "display_name": display_name,
                "speaker_key": str(grouping_key),
                "grouping_key": grouping_key,
                "segments": speaker_segments,
            }
        )

    entries.sort(key=lambda item: str(item["display_name"]).lower())
    return entries
