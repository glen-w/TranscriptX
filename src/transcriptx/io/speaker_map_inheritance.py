"""Speaker map application on managed transcript import.

Language variants of the same session (e.g. ``meeting_fr.json`` beside
``meeting.json``) can inherit speaker-map sidecars from the base transcript at
import time. ``speaker_id_to_db_id`` is copied because those IDs are canonical
cross-segment grouping keys shared by the same physical speakers.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import canonical_transcript_relpath
from transcriptx.core.utils.transcript_variant_paths import (
    base_transcript_path_for_flat_variant,
)
from transcriptx.io.speaker_map_resolver import SpeakerMapResolver, SpeakerMapState
from transcriptx.services.speaker_studio.mapping_service import SpeakerMappingService

logger = get_logger()


def _base_has_inheritable_speaker_state(state: SpeakerMapState) -> bool:
    return bool(state.speaker_map or state.ignored_speakers)


def _canonical_base_relpath(base_path: Path) -> str | None:
    try:
        return canonical_transcript_relpath(base_path).as_posix()
    except ValueError:
        return None


def try_inherit_speaker_map_from_base(variant_path: Path) -> bool:
    """Copy base speaker-map sidecar to a flat language variant when eligible.

    Returns True only when inheritance was performed. False means not inherited
    (fallback is handled by ``apply_speaker_map_on_import``).
    """
    variant_path = Path(variant_path)
    base_path = base_transcript_path_for_flat_variant(variant_path)
    if base_path is None:
        return False

    resolver = SpeakerMapResolver()
    if resolver.load_mapping(variant_path).has_sidecar:
        return False

    if not base_path.exists():
        return False

    base_state = resolver.load_mapping(base_path)
    if not base_state.has_sidecar or not _base_has_inheritable_speaker_state(
        base_state
    ):
        return False

    base_relpath = _canonical_base_relpath(base_path)
    if base_relpath is None:
        logger.debug(
            "Skipping speaker map inheritance for %s: base %s is outside transcripts_dir",
            variant_path,
            base_path,
        )
        return False

    SpeakerMappingService().bulk_update(
        str(variant_path),
        speaker_map=dict(base_state.speaker_map),
        ignored_speakers=list(base_state.ignored_speakers),
        method="batch",
        speaker_id_to_db_id=dict(base_state.speaker_id_to_db_id),
        speaker_map_source={
            "kind": "inherited_from_base",
            "base_transcript_relpath": base_relpath,
        },
    )
    logger.info(
        "Inherited speaker map for %s from base %s",
        variant_path.name,
        base_relpath,
    )
    return True


def _load_segments_from_json(transcript_path: Path) -> List[Any]:
    with open(transcript_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    segments = data.get("segments")
    if not segments or not isinstance(segments, list):
        raise ValueError("No segments found in transcript")
    return segments


def build_speaker_map_from_segments(segments: List[Any]) -> Dict[str, str]:
    """Extract stable speaker ID -> original speaker name from imported segments."""
    votes: dict[str, Counter[str]] = {}
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        speaker_id = seg.get("speaker")
        if not isinstance(speaker_id, str) or not speaker_id.strip():
            continue
        original_cue = seg.get("original_cue")
        if not isinstance(original_cue, dict):
            continue
        original_name = original_cue.get("original_speaker")
        if not isinstance(original_name, str) or not original_name.strip():
            continue
        sid = speaker_id.strip()
        name = original_name.strip()
        bucket = votes.setdefault(sid, Counter())
        bucket[name] += 1

    resolved: Dict[str, str] = {}
    for sid, counter in votes.items():
        if not counter:
            continue
        resolved[sid] = sorted(counter.items(), key=lambda item: (-item[1], item[0]))[
            0
        ][0]
    return resolved


def _apply_segment_derived_speaker_names(transcript_path: Path) -> None:
    try:
        segments = _load_segments_from_json(transcript_path)
    except ValueError:
        return
    speaker_map = build_speaker_map_from_segments(segments)
    if not speaker_map:
        return
    SpeakerMappingService().bulk_update(
        str(transcript_path),
        speaker_map=speaker_map,
        ignored_speakers=[],
        method="batch",
        speaker_map_source={"kind": "imported_original_speaker"},
    )


def apply_speaker_map_on_import(transcript_path: Path) -> None:
    """Apply speaker-map policy after managed import writes canonical JSON."""
    path = Path(transcript_path)
    if try_inherit_speaker_map_from_base(path):
        return
    if SpeakerMapResolver().load_mapping(path).has_sidecar:
        return
    _apply_segment_derived_speaker_names(path)
