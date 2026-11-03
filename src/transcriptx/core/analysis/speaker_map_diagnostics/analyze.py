"""Pure speaker-map / diarization consistency diagnostics (B19)."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from transcriptx.io.speaker_map_resolver import (
    is_effective_speaker_name,
    normalize_diarized_id,
    normalize_display_name,
)

SCHEMA_VERSION = 1
SEMANTIC_VERSION = "transcriptx.speaker_map_diagnostics.v1"

_PLACEHOLDER_PREFIX = "SPEAKER_"


def _segment_labels(segments: Sequence[Mapping[str, Any]]) -> list[str]:
    labels: list[str] = []
    for seg in segments:
        raw = seg.get("speaker")
        if raw is None or str(raw).strip() == "":
            continue
        labels.append(normalize_diarized_id(raw) or str(raw).strip())
    return labels


def _tier(
    *,
    named_count: int,
    unique_labels: int,
    treat_as_single: bool,
    allow_unnamed: bool,
) -> str:
    if named_count >= 1:
        return "T3"
    if treat_as_single:
        return "T1"
    if unique_labels >= 1 and allow_unnamed:
        return "T2"
    return "T0"


def compute_speaker_map_diagnostics(
    segments: Sequence[Mapping[str, Any]],
    *,
    speaker_map: Mapping[str, Any] | None = None,
    ignored_speakers: Sequence[str] | None = None,
    speaker_id_to_db_id: Mapping[str, Any] | None = None,
    treat_as_single_speaker: bool = False,
    allow_unnamed_speakers: bool = False,
    has_sidecar: bool = False,
) -> dict[str, Any]:
    """Diagnose map↔segment consistency. BYO SRT (no STT provenance) still runs."""
    mapping = {
        normalize_diarized_id(k) or str(k): normalize_display_name(v)
        for k, v in dict(speaker_map or {}).items()
    }
    ignored = {
        normalize_diarized_id(v) or str(v)
        for v in (ignored_speakers or [])
        if str(v).strip()
    }
    labels = _segment_labels(segments)
    unique_labels = sorted(set(labels))
    unnamed_labels = [
        lab
        for lab in unique_labels
        if lab.startswith(_PLACEHOLDER_PREFIX)
        and not is_effective_speaker_name(lab, mapping.get(lab, ""))
    ]
    named_labels = [
        lab
        for lab in unique_labels
        if is_effective_speaker_name(lab, mapping.get(lab, lab))
    ]
    map_keys = sorted(k for k in mapping if k)
    missing_from_segments = sorted(k for k in map_keys if k not in set(unique_labels))
    missing_from_map = sorted(lab for lab in unique_labels if lab not in mapping)
    display_counts = Counter(mapping[k] for k in named_labels if mapping.get(k))
    duplicate_display_names = sorted(
        name for name, n in display_counts.items() if n > 1
    )
    db_ids = dict(speaker_id_to_db_id or {})
    id_counts = Counter(str(v) for v in db_ids.values() if v not in (None, ""))
    voice_link_conflicts = sorted(vid for vid, n in id_counts.items() if n > 1)

    named_count = len(named_labels)
    status = "ok"
    if not unique_labels:
        status = "absent"
    elif missing_from_map or duplicate_display_names or voice_link_conflicts:
        status = "partial"

    return {
        "schema_version": SCHEMA_VERSION,
        "semantic_version": SEMANTIC_VERSION,
        "status": status,
        "has_sidecar": bool(has_sidecar),
        "speaker_tier": _tier(
            named_count=named_count,
            unique_labels=len(unique_labels),
            treat_as_single=treat_as_single_speaker,
            allow_unnamed=allow_unnamed_speakers,
        ),
        "segment_count": len(segments),
        "labeled_segment_count": len(labels),
        "unique_label_count": len(unique_labels),
        "named_speaker_count": named_count,
        "unnamed_labels": unnamed_labels,
        "named_labels": named_labels,
        "ignored_speakers": sorted(ignored),
        "map_keys_missing_from_segments": missing_from_segments,
        "segment_labels_missing_from_map": missing_from_map,
        "duplicate_display_names": duplicate_display_names,
        "voice_link_conflicts": voice_link_conflicts,
    }
