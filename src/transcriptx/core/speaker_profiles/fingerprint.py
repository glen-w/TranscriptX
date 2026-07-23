"""Occurrence fingerprint.v1 with frozen timestamp canonicalisation."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from transcriptx.core.speaker_profiles.versioning import OCCURRENCE_FINGERPRINT_PREFIX


def canonicalize_fingerprint_timestamp(value: Any) -> str | None:
    """Canonicalise a segment start/end for fingerprint hashing.

    Frozen rules:
    - int or float (finite) → float then ``format(x, ".6f")``
    - string that parses as finite float → same
    - non-finite or unparsable → ``None`` (timing-invalid; segment excluded)
    """
    if isinstance(value, bool):
        # bool is a subclass of int; treat as invalid for timestamps
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if not math.isfinite(number):
            return None
        return format(number, ".6f")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
        if not math.isfinite(number):
            return None
        return format(number, ".6f")
    return None


def fingerprint_segment_record(
    segment: Mapping[str, Any],
) -> dict[str, str] | None:
    """Build ordered fingerprint fields for one segment, or None if timing-invalid."""
    start = canonicalize_fingerprint_timestamp(segment.get("start"))
    end = canonicalize_fingerprint_timestamp(segment.get("end"))
    if start is None or end is None:
        return None
    text = segment.get("text")
    speaker = segment.get("speaker")
    return {
        "start": start,
        "end": end,
        "text": "" if text is None else str(text),
        "speaker": "" if speaker is None else str(speaker),
    }


def occurrence_fingerprint_records(
    segments: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    """Ordered fingerprint records for matching raw segments (timing-valid only)."""
    records: list[dict[str, str]] = []
    for segment in segments:
        record = fingerprint_segment_record(segment)
        if record is not None:
            records.append(record)
    return records


def compute_occurrence_fingerprint(
    segments: Sequence[Mapping[str, Any]],
) -> str:
    """Return ``occurrence_fingerprint.v1:<hex>`` for ordered matching segments."""
    records = occurrence_fingerprint_records(segments)
    encoded = json.dumps(
        records,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"{OCCURRENCE_FINGERPRINT_PREFIX}:{digest}"
