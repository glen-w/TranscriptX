"""
Speaker-map-derived vocabulary for Corrections Studio fuzzy detection.

Canonical fuzzy names come from the resolved sidecar map only (not segment traversal).
Observed named speakers in segments are diagnostics-only.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List

from transcriptx.core.utils.speaker_extraction import (
    clear_speaker_display_map,
    extract_speaker_info,
    get_speaker_display_name,
    set_speaker_display_map,
)
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    SpeakerMapState,
    normalize_display_name,
)
from transcriptx.services.corrections_studio.schema import FuzzySkippedReason
from transcriptx.utils.text_utils import is_named_speaker


@dataclass(frozen=True)
class FuzzySpeakerNameResolution:
    """Inputs for fuzzy detection + diagnostics."""

    display_names_for_fuzzy: List[str]
    observed_named_speakers: List[str]
    sidecar_loaded: bool
    map_entries: int
    load_failed: bool

    @property
    def map_had_entries_before_filter(self) -> bool:
        return self.map_entries > 0


def compute_speaker_map_fingerprint(state: SpeakerMapState) -> str:
    """
    Semantic fingerprint of the speaker map: canonical JSON (sorted keys, normalized
    values) — not raw sidecar bytes.
    """
    ignored = set(state.ignored_speakers)
    pairs: List[tuple[str, str]] = []
    for spk_id in sorted(state.speaker_map.keys()):
        if spk_id in ignored:
            continue
        name = normalize_display_name(state.speaker_map[spk_id])
        pairs.append((spk_id, name))
    canonical = json.dumps(pairs, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _map_derived_display_names_case_deduped(state: SpeakerMapState) -> List[str]:
    """Stable order: sorted speaker id; case-insensitive dedup keeping first-seen form."""
    ignored = set(state.ignored_speakers)
    ordered: List[str] = []
    seen_lower: set[str] = set()
    for spk_id in sorted(state.speaker_map.keys()):
        if spk_id in ignored:
            continue
        v = normalize_display_name(state.speaker_map[spk_id])
        if not v:
            continue
        lk = v.lower()
        if lk in seen_lower:
            continue
        seen_lower.add(lk)
        ordered.append(v)
    return ordered


def _collect_observed_named_speakers(
    segments: List[Dict[str, Any]], state: SpeakerMapState
) -> List[str]:
    """Named display labels seen on segments after applying the map (diagnostics only)."""
    if not state.speaker_map and not state.has_sidecar:
        return []
    try:
        set_speaker_display_map(dict(state.speaker_map))
        resolver = SpeakerMapResolver()
        resolved = resolver.resolve_segments(segments, state)
        out: List[str] = []
        seen: set[str] = set()
        for seg in resolved:
            info = extract_speaker_info(seg)
            if info is None:
                continue
            display = get_speaker_display_name(info.grouping_key, [seg], resolved)
            if not display or not is_named_speaker(display):
                continue
            if display in seen:
                continue
            seen.add(display)
            out.append(display)
        return out
    finally:
        clear_speaker_display_map()


def resolve_fuzzy_speaker_inputs(
    transcript_path: str,
    segments: List[Dict[str, Any]],
) -> FuzzySpeakerNameResolution:
    resolver = SpeakerMapResolver()
    load_failed = False
    try:
        state = resolver.load_mapping(transcript_path)
    except Exception:
        load_failed = True
        state = SpeakerMapState(has_sidecar=False)

    map_entries = len(state.speaker_map)

    if load_failed or not state.has_sidecar:
        return FuzzySpeakerNameResolution(
            display_names_for_fuzzy=[],
            observed_named_speakers=[],
            sidecar_loaded=False,
            map_entries=0,
            load_failed=load_failed,
        )

    if map_entries == 0:
        return FuzzySpeakerNameResolution(
            display_names_for_fuzzy=[],
            observed_named_speakers=[],
            sidecar_loaded=True,
            map_entries=0,
            load_failed=False,
        )

    normalized_values = _map_derived_display_names_case_deduped(state)
    display_names_for_fuzzy = [n for n in normalized_values if is_named_speaker(n)]

    observed = _collect_observed_named_speakers(segments, state)

    return FuzzySpeakerNameResolution(
        display_names_for_fuzzy=display_names_for_fuzzy,
        observed_named_speakers=observed,
        sidecar_loaded=True,
        map_entries=map_entries,
        load_failed=False,
    )


def compute_fuzzy_skipped_reason(
    fuzzy_enabled: bool,
    resolution: FuzzySpeakerNameResolution,
    fuzzy_named_speaker_count: int,
) -> FuzzySkippedReason:
    if not fuzzy_enabled:
        return FuzzySkippedReason.disabled
    if resolution.load_failed or not resolution.sidecar_loaded:
        return FuzzySkippedReason.no_speaker_map
    if resolution.map_entries == 0:
        return FuzzySkippedReason.zero_map_entries
    if fuzzy_named_speaker_count == 0:
        return FuzzySkippedReason.zero_named_speakers
    return FuzzySkippedReason.not_applicable
