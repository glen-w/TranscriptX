"""
SegmentIndexService: list transcripts and segments with deterministic speaker-map completeness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from transcriptx.core.utils.paths import DATA_DIR
from transcriptx.io.transcript_loader import load_segments
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    SpeakerMapState,
    normalize_diarized_id,
)
from transcriptx.core.utils._path_resolution import resolve_file_path
from transcriptx.core.utils._path_core import get_canonical_base_name

# Deterministic status for speaker-map completeness
SpeakerMapStatus = str  # "none" | "partial" | "complete"


@dataclass
class TranscriptSummary:
    """Summary of a transcript for picker UI and pipeline gating."""

    path: str
    base_name: str
    speaker_map_status: SpeakerMapStatus
    segment_count: int
    unique_speaker_count: int


@dataclass
class SegmentInfo:
    """One segment with speaker, times, text."""

    index: int
    start: float
    end: float
    text: str
    speaker: str  # diarized ID or display name
    speaker_diarized_id: Optional[str] = (
        None  # when segment has display name, the original ID if known
    )


# Match SPEAKER_00, SPEAKER_01, etc. (canonical form)
_DIARIZED_ID_RE = re.compile(r"^SPEAKER_\d+$", re.IGNORECASE)


def _is_diarized_id(s: str) -> bool:
    return bool(s and _DIARIZED_ID_RE.match(s.strip()))


def _compute_speaker_map_status(
    segments: List[dict],
    state: SpeakerMapState,
) -> SpeakerMapStatus:
    """
    Deterministic completeness: none | partial | complete.
    Every diarized ID present in segments must be either in the sidecar's
    speaker_map (with a non-empty name) or in ignored_speakers.
    """
    speaker_map = state.speaker_map
    ignored_speakers = state.ignored_speakers
    if not state.has_sidecar and not speaker_map and not ignored_speakers:
        return "none"
    if not segments:
        return "complete" if state.has_named_speakers or ignored_speakers else "none"

    # Unique speaker values that appear in segments
    unique_in_segments = set()
    for seg in segments:
        sp = seg.get("speaker")
        if sp is None or not str(sp).strip():
            continue
        unique_in_segments.add(str(sp).strip())

    diarized_ids_in_segments = {sp for sp in unique_in_segments if _is_diarized_id(sp)}
    ignored_set = set(ignored_speakers or [])
    covered = set(speaker_map.keys()) | ignored_set
    mapped_with_name = {
        k for k, v in (speaker_map or {}).items() if v and str(v).strip()
    }

    # Compare using normalized IDs so SPEAKER_1 in segments matches SPEAKER_01 in sidecar.
    for did in diarized_ids_in_segments:
        nid = normalize_diarized_id(did)
        if not nid:
            continue
        if nid not in covered:
            return "partial"
        if nid in ignored_set:
            continue
        if nid not in mapped_with_name:
            return "partial"
    return "complete"


class SegmentIndexService:
    """Read-only index: list transcripts with speaker-map status and load segments."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self._data_dir = Path(data_dir) if data_dir else Path(DATA_DIR)

    def list_transcripts(
        self,
        data_dir: Optional[Path] = None,
        *,
        canonical_only: bool = True,
    ) -> List[TranscriptSummary]:
        """
        Enumerate transcripts under data_dir/transcripts with deterministic speaker_map_status.
        If data_dir is None, uses self._data_dir.
        """
        root = Path(data_dir) if data_dir else self._data_dir
        transcripts_dir = root / "transcripts"
        if not transcripts_dir.is_dir():
            return []

        # Skip known non-transcript JSON files when including all .json
        _skip_filenames = frozenset(
            {"manifest.json", "processing_state.json", "config.json"}
        )

        summaries: List[TranscriptSummary] = []
        for path in sorted(transcripts_dir.glob("*.json")):
            if path.name in _skip_filenames:
                continue
            if canonical_only and not path.name.endswith("_transcriptx.json"):
                continue
            try:
                segments = load_segments(str(path))
                if not segments:
                    continue
                state = SpeakerMapResolver().load_mapping(str(path))
                status = _compute_speaker_map_status(segments, state)
                unique_speakers = len(
                    set(seg.get("speaker") for seg in segments if seg.get("speaker"))
                )
                summaries.append(
                    TranscriptSummary(
                        path=str(path.resolve()),
                        base_name=get_canonical_base_name(str(path)),
                        speaker_map_status=status,
                        segment_count=len(segments),
                        unique_speaker_count=unique_speakers,
                    )
                )
            except Exception:
                continue
        return summaries

    def summary_for_path(self, path: str | Path) -> Optional[TranscriptSummary]:
        """
        Build a single TranscriptSummary for a path, or None if not loadable.
        Used when listing from an external source (e.g. discover_all_transcript_paths).
        """
        path = Path(path)
        if not path.is_file() or path.suffix.lower() != ".json":
            return None
        skip = frozenset({"manifest.json", "processing_state.json", "config.json"})
        if path.name in skip:
            return None
        try:
            segments = load_segments(str(path))
            if not segments:
                return None
            state = SpeakerMapResolver().load_mapping(str(path))
            status = _compute_speaker_map_status(segments, state)
            unique_speakers = len(
                set(seg.get("speaker") for seg in segments if seg.get("speaker"))
            )
            return TranscriptSummary(
                path=str(path.resolve()),
                base_name=get_canonical_base_name(str(path)),
                speaker_map_status=status,
                segment_count=len(segments),
                unique_speaker_count=unique_speakers,
            )
        except Exception:
            return None

    def list_segments(self, transcript_path: str) -> List[SegmentInfo]:
        """Load segments for a transcript with start, end, text, speaker."""
        raw = load_segments(transcript_path)
        state = SpeakerMapResolver().load_mapping(transcript_path)
        resolver = SpeakerMapResolver()
        resolved = resolver.resolve_segments(raw, state)
        result: List[SegmentInfo] = []
        for i, (raw_seg, seg) in enumerate(zip(raw, resolved)):
            start = seg.get("start") or seg.get("start_time") or 0.0
            end = seg.get("end") or seg.get("end_time") or 0.0
            if "start_ms" in seg and "end_ms" in seg:
                start = seg["start_ms"] / 1000.0
                end = seg["end_ms"] / 1000.0
            text = (seg.get("text") or "").strip()
            sp = seg.get("speaker") or ""
            diarized_id: Optional[str] = None
            raw_speaker = raw_seg.get("speaker")
            if raw_speaker is not None and _is_diarized_id(str(raw_speaker)):
                diarized_id = normalize_diarized_id(str(raw_speaker))
            result.append(
                SegmentInfo(
                    index=i,
                    start=float(start),
                    end=float(end),
                    text=text,
                    speaker=sp,
                    speaker_diarized_id=diarized_id,
                )
            )
        return result

    def get_transcript_audio_path(self, transcript_path: str) -> Optional[Path]:
        """Resolve audio file for transcript; returns None if not found."""
        try:
            resolved = resolve_file_path(transcript_path, file_type="audio")
            p = Path(resolved)
            return p if p.exists() else None
        except Exception:
            return None
