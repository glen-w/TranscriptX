"""G1 transcript stitch: concatenate already-transcribed parts into one canonical.

Abort rather than corrupt library identity. Audio-only merge stays in
``core.audio.conversion.merge_audio_files``. This module never overwrites
managed originals.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Sequence

STITCH_SCHEMA_VERSION = 1
_DURATION_SLACK_SECONDS = 1.0


class TranscriptStitchError(ValueError):
    """Identity-unsafe stitch: refuse and leave parts intact."""


def _segment_end(seg: dict[str, Any]) -> float | None:
    for key in ("end", "end_time", "endTime"):
        if key in seg and seg[key] is not None:
            try:
                return float(seg[key])
            except (TypeError, ValueError):
                return None
    start = _segment_start(seg)
    dur = seg.get("duration")
    if start is not None and dur is not None:
        try:
            return start + float(dur)
        except (TypeError, ValueError):
            return None
    return None


def _segment_start(seg: dict[str, Any]) -> float | None:
    for key in ("start", "start_time", "startTime"):
        if key in seg and seg[key] is not None:
            try:
                return float(seg[key])
            except (TypeError, ValueError):
                return None
    return None


def rebase_segments(
    segments: Sequence[dict[str, Any]], offset: float
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for seg in segments:
        row = copy.deepcopy(seg)
        start = _segment_start(row)
        end = _segment_end(row)
        if start is not None:
            row["start"] = round(start + offset, 3)
        if end is not None:
            row["end"] = round(end + offset, 3)
        words = row.get("words")
        if isinstance(words, list):
            shifted: list[Any] = []
            for word in words:
                if not isinstance(word, dict):
                    shifted.append(word)
                    continue
                w = dict(word)
                for key in ("start", "end"):
                    if key in w and w[key] is not None:
                        try:
                            w[key] = round(float(w[key]) + offset, 3)
                        except (TypeError, ValueError):
                            pass
                shifted.append(w)
            row["words"] = shifted
        out.append(row)
    return out


def declared_duration_seconds(doc: MappingLike) -> float | None:
    meta = doc.get("metadata") if isinstance(doc.get("metadata"), dict) else {}
    for key in ("duration", "duration_seconds"):
        if meta.get(key) is not None:
            try:
                return float(meta[key])
            except (TypeError, ValueError):
                return None
    return None


def part_duration_seconds(doc: MappingLike) -> float:
    declared = declared_duration_seconds(doc)
    if declared is not None:
        return declared
    segs = list(doc.get("segments") or [])
    ends = [_segment_end(s) for s in segs if isinstance(s, dict)]
    numeric = [e for e in ends if e is not None]
    if numeric:
        return float(max(numeric))
    return 0.0


MappingLike = dict[str, Any]


def stitch_transcript_documents(
    parts: Sequence[MappingLike],
    *,
    source_stems: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Merge ordered canonical documents. Keep SPEAKER_* labels; do not invent T2 names."""
    if len(parts) < 2:
        raise TranscriptStitchError("Need at least two transcript parts to stitch")
    offset = 0.0
    merged_segments: list[dict[str, Any]] = []
    provenance_parts: list[dict[str, Any]] = []
    for idx, doc in enumerate(parts):
        segs = [s for s in (doc.get("segments") or []) if isinstance(s, dict)]
        duration = part_duration_seconds(doc)
        last_end = 0.0
        ends = [_segment_end(s) for s in segs]
        numeric_ends = [e for e in ends if e is not None]
        if numeric_ends:
            last_end = float(max(numeric_ends))
            declared = declared_duration_seconds(doc)
            if declared is not None and abs(declared - last_end) > max(
                _DURATION_SLACK_SECONDS, 0.05 * declared
            ):
                raise TranscriptStitchError(
                    f"Part {idx + 1}: duration {declared:.3f}s vs last segment "
                    f"end {last_end:.3f}s cannot be reconciled"
                )
        merged_segments.extend(rebase_segments(segs, offset))
        step = duration if duration > 0 else last_end
        stem = None
        if source_stems and idx < len(source_stems):
            stem = source_stems[idx]
        provenance_parts.append(
            {
                "index": idx,
                "stem": stem,
                "offset_seconds": round(offset, 3),
                "duration_seconds": round(step, 3),
                "segment_count": len(segs),
            }
        )
        offset += step

    first = dict(parts[0])
    metadata = dict(first.get("metadata") or {})
    metadata["duration"] = round(offset, 3)
    metadata["language"] = metadata.get("language") or "en"
    return {
        "schema_version": first.get("schema_version", 1),
        "source": first.get("source") or "transcript_stitch",
        "metadata": metadata,
        "segments": merged_segments,
        "stitch": {
            "schema_version": STITCH_SCHEMA_VERSION,
            "part_count": len(parts),
            "parts": provenance_parts,
        },
    }


def write_stitched_transcript(
    dest: str | Path,
    document: MappingLike,
) -> Path:
    """Write a new canonical JSON. Caller must not pass a managed original path."""
    import json

    path = Path(dest)
    if path.exists():
        raise TranscriptStitchError(
            f"Refusing to overwrite existing transcript: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path
