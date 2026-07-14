"""Transcript formatting, deterministic truncation, and bounded prompt building."""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from transcriptx.core.llm.prompting import (
    DEFAULT_CLOSE_DELIMITER,
    DEFAULT_OPEN_DELIMITER,
    build_prompt_envelope,
    llm_prompt_overhead_chars,
)
from transcriptx.core.utils.speaker_extraction import resolve_segment_speaker_label

__all__ = [
    "format_transcript_lines",
    "truncate_transcript_block",
    "build_bounded_user_prompt",
]

_UNNAMED_SPEAKER_LABEL = "Speaker"
_OMISSION_MARKER = "\n\n[... transcript content omitted ...]\n\n"


def format_transcript_lines(segments: List[Dict[str, Any]]) -> List[str]:
    """Build ordered ``Speaker: text`` lines, skipping empty segments."""
    lines: List[str] = []
    for seg in segments:
        text = " ".join(str(seg.get("text", "")).split())
        if not text:
            continue
        speaker = resolve_segment_speaker_label(seg, segments, None)
        if not speaker or speaker == "Unknown":
            speaker = _UNNAMED_SPEAKER_LABEL
        lines.append(f"{speaker}: {text}")
    return lines


def _segment_join_len(indices: List[int], lines: List[str]) -> int:
    if not indices:
        return 0
    total = sum(len(lines[i]) for i in indices)
    total += max(0, len(indices) - 1)
    return total


def _collect_segment_indices(
    lines: List[str],
    *,
    start: int,
    end: int,
    step: int,
    max_len: int,
    excluded: Set[int],
) -> List[int]:
    indices: List[int] = []
    used = 0
    i = start
    while (step > 0 and i < end) or (step < 0 and i >= end):
        if i in excluded:
            i += step
            continue
        add = len(lines[i]) + (1 if indices else 0)
        if used + add > max_len:
            break
        indices.append(i)
        used += add
        i += step
    return indices


def _grow_segment_indices(
    lines: List[str],
    indices: List[int],
    *,
    start: int,
    end: int,
    step: int,
    max_extra: int,
    excluded: Set[int],
) -> List[int]:
    if max_extra <= 0:
        return indices
    used = _segment_join_len(indices, lines)
    grown = list(indices)
    i = start
    while (step > 0 and i < end) or (step < 0 and i >= end):
        if i in excluded or i in grown:
            i += step
            continue
        add = len(lines[i]) + (1 if grown else 0)
        if used + add > max_extra:
            break
        grown.append(i)
        used += add
        i += step
    if step < 0:
        grown.sort()
    return grown


def truncate_transcript_block(
    lines: List[str],
    *,
    max_chars: int,
    omission_marker: str = _OMISSION_MARKER,
) -> Tuple[str, Dict[str, Any]]:
    """
    Truncate formatted transcript lines at segment boundaries.

    Uses a deterministic 60/40 head-plus-tail split when possible; falls back to
    single-segment hard truncate.
    """
    total_segments = len(lines)
    if total_segments == 0:
        return "", {
            "total_segments": 0,
            "included_segments": 0,
            "partially_included_segments": 0,
            "omitted_segments": 0,
            "truncated": False,
            "truncation_strategy": "none",
        }

    full_text = "\n".join(lines)
    if len(full_text) <= max_chars:
        return full_text, {
            "total_segments": total_segments,
            "included_segments": total_segments,
            "partially_included_segments": 0,
            "omitted_segments": 0,
            "truncated": False,
            "truncation_strategy": "none",
        }

    marker_len = len(omission_marker)
    content_budget = max(0, max_chars - marker_len)
    head_alloc = int(content_budget * 0.6)
    tail_alloc = content_budget - head_alloc

    head_indices = _collect_segment_indices(
        lines,
        start=0,
        end=total_segments,
        step=1,
        max_len=head_alloc,
        excluded=set(),
    )
    head_set = set(head_indices)
    tail_indices = _collect_segment_indices(
        lines,
        start=total_segments - 1,
        end=-1,
        step=-1,
        max_len=tail_alloc,
        excluded=head_set,
    )
    tail_indices.sort()

    head_used = _segment_join_len(head_indices, lines)
    tail_used = _segment_join_len(tail_indices, lines)
    unused_head = head_alloc - head_used
    if unused_head > 0 and tail_indices:
        tail_indices = _grow_segment_indices(
            lines,
            tail_indices,
            start=total_segments - 1,
            end=-1,
            step=-1,
            max_extra=tail_used + unused_head,
            excluded=head_set,
        )
        tail_used = _segment_join_len(tail_indices, lines)

    tail_set = set(tail_indices)
    unused_tail = tail_alloc - tail_used
    if unused_tail > 0 and head_indices:
        head_indices = _grow_segment_indices(
            lines,
            head_indices,
            start=0,
            end=total_segments,
            step=1,
            max_extra=head_used + unused_tail,
            excluded=tail_set,
        )
        head_set = set(head_indices)

    included = head_set | tail_set
    omitted = total_segments - len(included)

    if not head_indices and not tail_indices:
        line_budget = content_budget if total_segments > 1 else max_chars
        if total_segments > 1:
            line_budget = max(0, max_chars - marker_len)
        truncated_line = lines[0][:line_budget]
        if total_segments > 1 and truncated_line:
            combined = f"{truncated_line}{omission_marker}"
            if len(combined) > max_chars:
                combined = combined[:max_chars]
        else:
            combined = truncated_line[:max_chars]
        return combined, {
            "total_segments": total_segments,
            "included_segments": 1,
            "partially_included_segments": 1,
            "omitted_segments": max(0, total_segments - 1),
            "truncated": True,
            "truncation_strategy": "single_segment_hard_truncate",
        }

    head_part = "\n".join(lines[i] for i in head_indices)
    tail_part = "\n".join(lines[i] for i in tail_indices)
    if omitted > 0:
        if tail_part:
            combined = f"{head_part}{omission_marker}{tail_part}"
        else:
            combined = f"{head_part}{omission_marker}"
    else:
        combined = f"{head_part}\n{tail_part}" if tail_part else head_part

    if len(combined) > max_chars:
        while len(combined) > max_chars and (head_indices or tail_indices):
            if tail_indices and (
                not head_indices or len(tail_indices) >= len(head_indices)
            ):
                tail_indices.pop()
            elif head_indices:
                head_indices.pop()
            else:
                break
            head_part = "\n".join(lines[i] for i in head_indices)
            tail_part = "\n".join(lines[i] for i in tail_indices)
            included = set(head_indices) | set(tail_indices)
            omitted = total_segments - len(included)
            if omitted > 0:
                combined = (
                    f"{head_part}{omission_marker}{tail_part}"
                    if tail_part
                    else f"{head_part}{omission_marker}"
                )
            else:
                combined = f"{head_part}\n{tail_part}" if tail_part else head_part

    return combined, {
        "total_segments": total_segments,
        "included_segments": len(set(head_indices) | set(tail_indices)),
        "partially_included_segments": 0,
        "omitted_segments": omitted,
        "truncated": True,
        "truncation_strategy": "head_tail",
    }


def build_bounded_user_prompt(
    *,
    instruction: str,
    transcript_block: str,
    max_input_chars: int,
    open_delimiter: str = DEFAULT_OPEN_DELIMITER,
    close_delimiter: str = DEFAULT_CLOSE_DELIMITER,
) -> Tuple[str, Dict[str, Any]]:
    """
    Build the full user prompt respecting ``max_input_chars``.

    Instruction and delimiters are counted against the budget.
    """
    prefix, suffix = build_prompt_envelope(
        instruction=instruction,
        open_delimiter=open_delimiter,
        close_delimiter=close_delimiter,
    )
    overhead = llm_prompt_overhead_chars(
        instruction=instruction,
        open_delimiter=open_delimiter,
        close_delimiter=close_delimiter,
    )
    transcript_budget = max(0, max_input_chars - overhead)
    line_list = transcript_block.split("\n") if transcript_block else []

    truncated_block = ""
    trunc_meta: Dict[str, Any] = {
        "total_segments": len(line_list),
        "included_segments": 0,
        "partially_included_segments": 0,
        "omitted_segments": 0,
        "truncated": False,
        "truncation_strategy": "none",
    }
    for budget in range(transcript_budget, -1, -1):
        truncated_block, trunc_meta = truncate_transcript_block(
            line_list,
            max_chars=budget,
        )
        prompt = f"{prefix}{truncated_block}{suffix}"
        if len(prompt) <= max_input_chars:
            break

    prompt = f"{prefix}{truncated_block}{suffix}"
    meta = dict(trunc_meta)
    meta["input_chars"] = len(prompt)
    meta["transcript_chars_total"] = len(transcript_block or "")
    meta["transcript_chars_used"] = len(truncated_block)
    return prompt, meta
