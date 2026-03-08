"""
SpeakerMappingService: sole writer for speaker mapping.
Delegates transcript JSON I/O to TranscriptStore (lockfile + atomic write + normalization).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx.core.store import TranscriptStore
from transcriptx.core.utils.logger import get_logger
from transcriptx.io.transcript_loader import (
    extract_speaker_map_from_transcript,
    extract_ignored_speakers_from_transcript,
    load_transcript,
)
from transcriptx.io.speaker_mapping.core import (
    _apply_speaker_map_to_data,
    _SPEAKER_MAP_METHODS,
)

logger = get_logger()
_store = TranscriptStore()

# Canonical diarized ID: SPEAKER_00, SPEAKER_01, ...
_DIARIZED_RE = re.compile(r"^speaker[_\-]?\s*(\d+)$", re.IGNORECASE)


def _normalize_diarized_id(s: str) -> str:
    """Normalize to stable SPEAKER_XX form."""
    if not s or not str(s).strip():
        return s
    s = str(s).strip()
    m = _DIARIZED_RE.match(s)
    if m:
        return f"SPEAKER_{int(m.group(1)):02d}"
    # Already SPEAKER_XX or unknown; uppercase if looks like SPEAKER_NN
    if s.upper().startswith("SPEAKER_") and s.upper()[8:].isdigit():
        return s.upper()
    return s


def _normalize_display_name(s: str) -> str:
    """Trim and collapse internal whitespace."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s).strip())


@dataclass
class SpeakerMapState:
    """Current mapping state for a transcript."""

    speaker_map: Dict[str, str]
    ignored_speakers: List[str]
    schema_version: str
    provenance: Optional[Dict[str, Any]]


class SpeakerMappingService:
    """
    Single writer for speaker mapping. Uses lockfile and atomic write (.tmp then replace).
    All mapping writes (CLI and web) should go through this service.
    """

    def get_mapping(self, transcript_path: str) -> SpeakerMapState:
        """Read current mapping from transcript JSON (no lock)."""
        path = Path(transcript_path)
        if not path.exists():
            return SpeakerMapState(
                speaker_map={},
                ignored_speakers=[],
                schema_version="1.0",
                provenance=None,
            )
        speaker_map = extract_speaker_map_from_transcript(transcript_path)
        ignored = extract_ignored_speakers_from_transcript(path)
        try:
            data = load_transcript(transcript_path)
            schema = data.get("speaker_map_schema_version", "1.0")
            prov = data.get("speaker_map_provenance")
        except Exception:
            schema = "1.0"
            prov = None
        return SpeakerMapState(
            speaker_map=speaker_map or {},
            ignored_speakers=ignored or [],
            schema_version=schema,
            provenance=prov,
        )

    def _apply_and_stamp(
        self,
        data: Dict[str, Any],
        method: str,
    ) -> None:
        """Apply speaker map provenance and segment rewrites to data (in place)."""
        method = method if method in _SPEAKER_MAP_METHODS else "interactive"
        speaker_id_to_db_id = data.get("_speaker_id_to_db_id") or data.get(
            "speaker_id_to_db_id"
        )
        _apply_speaker_map_to_data(
            data,
            data["speaker_map"],
            speaker_id_to_db_id=speaker_id_to_db_id,
            ignored_speakers=data.get("ignored_speakers"),
            rewrite_segment_speakers=True,
            speaker_map_source=data.get("speaker_map_source"),
            method=method,
        )
        data.pop("_speaker_id_to_db_id", None)

    def assign_speaker(
        self,
        transcript_path: str,
        diarized_id: str,
        display_name: str,
        *,
        method: str = "web",
    ) -> SpeakerMapState:
        """Set one diarized ID to a display name."""
        did = _normalize_diarized_id(diarized_id)
        name = _normalize_display_name(display_name)
        path = Path(transcript_path)
        if not path.exists():
            raise FileNotFoundError(transcript_path)

        def mutator(data: Dict[str, Any]) -> None:
            speaker_map = data.get("speaker_map") or {}
            speaker_map[did] = name
            data["speaker_map"] = speaker_map
            data.setdefault("ignored_speakers", data.get("ignored_speakers") or [])
            data["_speaker_id_to_db_id"] = data.get("speaker_id_to_db_id") or {}
            self._apply_and_stamp(data, method)

        _store.mutate(transcript_path, mutator, reason="speaker_mapping", timeout=15)
        return self.get_mapping(transcript_path)

    def ignore_speaker(
        self,
        transcript_path: str,
        diarized_id: str,
        *,
        method: str = "web",
    ) -> SpeakerMapState:
        """Add diarized ID to ignored_speakers."""
        did = _normalize_diarized_id(diarized_id)
        path = Path(transcript_path)
        if not path.exists():
            raise FileNotFoundError(transcript_path)

        def mutator(data: Dict[str, Any]) -> None:
            ignored = list(data.get("ignored_speakers") or [])
            if did not in ignored:
                ignored.append(did)
            data["ignored_speakers"] = ignored
            data["_speaker_id_to_db_id"] = data.get("speaker_id_to_db_id") or {}
            self._apply_and_stamp(data, method)

        _store.mutate(transcript_path, mutator, reason="speaker_mapping", timeout=15)
        return self.get_mapping(transcript_path)

    def unignore_speaker(
        self,
        transcript_path: str,
        diarized_id: str,
        *,
        method: str = "web",
    ) -> SpeakerMapState:
        """Remove diarized ID from ignored_speakers list."""
        did = _normalize_diarized_id(diarized_id)
        path = Path(transcript_path)
        if not path.exists():
            raise FileNotFoundError(transcript_path)

        def mutator(data: Dict[str, Any]) -> None:
            ignored = list(data.get("ignored_speakers") or [])
            if did in ignored:
                ignored.remove(did)
            data["ignored_speakers"] = ignored
            data["_speaker_id_to_db_id"] = data.get("speaker_id_to_db_id") or {}
            self._apply_and_stamp(data, method)

        _store.mutate(transcript_path, mutator, reason="speaker_mapping", timeout=15)
        return self.get_mapping(transcript_path)

    def bulk_update(
        self,
        transcript_path: str,
        speaker_map: Dict[str, str],
        ignored_speakers: List[str],
        *,
        method: str = "batch",
        speaker_map_source: Optional[Dict[str, Any]] = None,
        speaker_id_to_db_id: Optional[Dict[str, int]] = None,
    ) -> SpeakerMapState:
        """Replace mapping and ignored list (e.g. from CLI batch or import)."""
        path = Path(transcript_path)
        if not path.exists():
            raise FileNotFoundError(transcript_path)
        normalized_map = {
            _normalize_diarized_id(k): _normalize_display_name(v)
            for k, v in speaker_map.items()
        }
        normalized_ignored = [
            _normalize_diarized_id(s) for s in (ignored_speakers or [])
        ]

        def mutator(data: Dict[str, Any]) -> None:
            data["speaker_map"] = normalized_map
            data["ignored_speakers"] = normalized_ignored
            data["_speaker_id_to_db_id"] = (
                speaker_id_to_db_id or data.get("speaker_id_to_db_id") or {}
            )
            if speaker_map_source is not None:
                data["speaker_map_source"] = speaker_map_source
            self._apply_and_stamp(data, method)

        _store.mutate(transcript_path, mutator, reason="speaker_mapping", timeout=15)
        return self.get_mapping(transcript_path)
