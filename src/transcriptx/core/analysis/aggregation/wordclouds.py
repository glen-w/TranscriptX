"""
Group aggregation for wordclouds.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple

from transcriptx.core.pipeline.result_envelope import (  # type: ignore[import]
    PerTranscriptResult,
)
from transcriptx.core.pipeline.speaker_normalizer import (  # type: ignore[import]
    CanonicalSpeakerMap,
)
from transcriptx.core.utils.speaker_extraction import (  # type: ignore[import]
    extract_speaker_info,
)
from transcriptx.core.utils.nlp_utils import tokenize_and_filter  # type: ignore[import]
from transcriptx.io.transcript_service import TranscriptService  # type: ignore[import]
from transcriptx.utils.text_utils import is_named_speaker  # type: ignore[import]


def segment_order_key(segment: Dict[str, Any]) -> tuple:
    """Within a transcript: timestamp when present, else stable list order."""
    for key in ("start", "start_time", "begin", "offset"):
        v = segment.get(key)
        if isinstance(v, (int, float)):
            return (0, float(v))
    return (1, 0.0)


def build_full_transcript_text_pooled(
    per_transcript_results: List[PerTranscriptResult],
) -> str | None:
    """
    Concatenate all segment text across members (includes unidentified/unmapped).
    Member order: ``order_index``. Segment order: ``segment_order_key``.
    """
    transcript_service = TranscriptService(enable_cache=True)
    lines: List[str] = []
    for result in sorted(per_transcript_results, key=lambda r: r.order_index):
        path = result.transcript_path
        if not path:
            continue
        segments = transcript_service.load_segments(path, use_cache=True)
        segments = sorted(segments, key=segment_order_key)
        for segment in segments:
            raw = segment.get("text", "")
            if raw and str(raw).strip():
                lines.append(_normalize_text(str(raw)))
    if not lines:
        return None
    return "\n".join(lines)


def _normalize_text(text: str) -> str:
    return " ".join(text.split())


def resolve_segment_canonical_display(
    segment: Dict[str, Any],
    transcript_path: str,
    canonical_speaker_map: CanonicalSpeakerMap,
) -> Optional[str]:
    info = extract_speaker_info(segment)
    if info is None:
        return None

    if not is_named_speaker(info.display_name):
        return None

    local_to_canonical = canonical_speaker_map.transcript_to_speakers.get(
        transcript_path, {}
    )
    canonical_id = local_to_canonical.get(info.grouping_key)
    if canonical_id is None:
        return None

    display_name = canonical_speaker_map.canonical_to_display.get(canonical_id)
    if isinstance(display_name, str):
        return display_name
    return info.display_name


def _build_grouped_hash(grouped: Dict[str, List[str]]) -> str:
    canonical_items = []
    for speaker in sorted(grouped.keys()):
        chunks = sorted(grouped[speaker])
        text = "\n".join(chunks)
        canonical_items.append({"speaker": speaker, "text": text})
    payload = json.dumps(canonical_items, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def aggregate_wordclouds_group(
    per_transcript_results: List[PerTranscriptResult],
    canonical_speaker_map: CanonicalSpeakerMap,
) -> Tuple[Dict[str, List[str]] | None, Dict[str, Any] | None]:
    """
    Aggregate per-transcript segments into grouped text by canonical speaker.

    Returns grouped text and a summary dict. Returns (None, None) if no text.
    """
    grouped: Dict[str, List[str]] = {}
    excluded_speakers = set()
    excluded_chunks = 0
    excluded_chars = 0

    transcript_service = TranscriptService(enable_cache=True)

    for result in per_transcript_results:
        transcript_path = result.transcript_path
        if not transcript_path:
            raise ValueError("PerTranscriptResult.transcript_path is required")

        segments = transcript_service.load_segments(transcript_path, use_cache=True)
        for segment in segments:
            raw_text = segment.get("text", "")
            if not raw_text or not raw_text.strip():
                continue
            cleaned_text = _normalize_text(raw_text)
            if not cleaned_text:
                continue

            info = extract_speaker_info(segment)
            if info is None:
                speaker_label = segment.get("speaker")
                if speaker_label and not is_named_speaker(str(speaker_label)):
                    excluded_speakers.add(str(speaker_label))
                excluded_chunks += 1
                excluded_chars += len(cleaned_text)
                continue

            if not is_named_speaker(info.display_name):
                excluded_speakers.add(info.display_name)
                excluded_chunks += 1
                excluded_chars += len(cleaned_text)
                continue

            display_name = resolve_segment_canonical_display(
                segment, transcript_path, canonical_speaker_map
            )
            if display_name is None:
                excluded_speakers.add(info.display_name)
                excluded_chunks += 1
                excluded_chars += len(cleaned_text)
                continue

            grouped.setdefault(display_name, []).append(cleaned_text)

    if not grouped:
        return None, None

    grouped_joined = {speaker: "\n".join(chunks) for speaker, chunks in grouped.items()}
    total_chunks = sum(len(chunks) for chunks in grouped.values())
    total_chars = sum(len(text) for text in grouped_joined.values())
    global_text_sorted = "\n".join(
        grouped_joined[s] for s in sorted(grouped_joined.keys())
    )
    total_tokens = (
        len(tokenize_and_filter(global_text_sorted)) if global_text_sorted else 0
    )

    from transcriptx.core.output.group_wordcloud_output_service import (
        CANONICAL_MERGE_BASIS_VALUE,
    )

    summary: Dict[str, Any] = {
        "speaker_count": len(grouped),
        "speakers": sorted(grouped.keys()),
        "per_speaker_chunk_counts": {
            speaker: len(chunks) for speaker, chunks in grouped.items()
        },
        "total_chunks": total_chunks,
        "total_chars": total_chars,
        "total_tokens": total_tokens,
        "global_includes_unidentified": False,
        "excluded_speakers": sorted(excluded_speakers),
        "excluded_chunks": excluded_chunks,
        "excluded_chars": excluded_chars,
        "grouped_hash": _build_grouped_hash(grouped),
        "canonical_merge_basis": CANONICAL_MERGE_BASIS_VALUE,
        "cross_bucket_global_join_order": "sorted_speaker_display_name",
    }

    return grouped, summary
