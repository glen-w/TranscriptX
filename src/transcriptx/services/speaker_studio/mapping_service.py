"""Speaker mapping service backed by sidecar files."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from transcriptx import __version__ as _transcriptx_version
from transcriptx.core.store import SidecarStore
from transcriptx.io.speaker_map_resolver import (
    SpeakerMapResolver,
    SpeakerMapState,
    normalize_diarized_id,
    normalize_display_name,
    sidecar_path_for,
)

_sidecar_store = SidecarStore()
_resolver = SpeakerMapResolver(_sidecar_store)

_SPEAKER_MAP_METHODS = ("interactive", "web", "batch")


def _sidecar_provenance(method: str) -> Dict[str, Any]:
    return {
        "tool": "transcriptx",
        "version": _transcriptx_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": method if method in _SPEAKER_MAP_METHODS else "interactive",
    }


class SpeakerMappingService:
    """Single writer for speaker mapping sidecars."""

    def get_mapping(self, transcript_path: str) -> SpeakerMapState:
        """Read current mapping from the sidecar."""
        return _resolver.load_mapping(transcript_path)

    def _mutate_sidecar(
        self,
        transcript_path: str,
        mutator,
    ) -> None:
        sidecar = sidecar_path_for(transcript_path)
        _sidecar_store.mutate(sidecar, mutator, reason="speaker_mapping", timeout=15)

    def assign_speaker(
        self,
        transcript_path: str,
        diarized_id: str,
        display_name: str,
        *,
        method: str = "web",
    ) -> SpeakerMapState:
        """Set one diarized ID to a display name in the sidecar."""
        did = normalize_diarized_id(diarized_id)
        name = normalize_display_name(display_name)
        path = Path(transcript_path)
        if not path.exists():
            raise FileNotFoundError(transcript_path)

        def mutator(data: Dict[str, Any]) -> None:
            speaker_map = dict(data.get("speaker_map") or {})
            speaker_map[did] = name
            data["speaker_map"] = speaker_map
            ignored = [
                normalize_diarized_id(s) for s in data.get("ignored_speakers") or []
            ]
            data["ignored_speakers"] = list(dict.fromkeys([s for s in ignored if s]))
            data["speaker_map_schema_version"] = 1
            data["speaker_map_provenance"] = _sidecar_provenance(method)
            if "speaker_id_to_db_id" not in data:
                data["speaker_id_to_db_id"] = {}

        self._mutate_sidecar(transcript_path, mutator)
        return self.get_mapping(transcript_path)

    def ignore_speaker(
        self,
        transcript_path: str,
        diarized_id: str,
        *,
        method: str = "web",
    ) -> SpeakerMapState:
        """Add diarized ID to ignored_speakers in the sidecar."""
        did = normalize_diarized_id(diarized_id)
        path = Path(transcript_path)
        if not path.exists():
            raise FileNotFoundError(transcript_path)

        def mutator(data: Dict[str, Any]) -> None:
            ignored = list(data.get("ignored_speakers") or [])
            if did not in ignored:
                ignored.append(did)
            data["ignored_speakers"] = list(
                dict.fromkeys([normalize_diarized_id(s) for s in ignored if s])
            )
            data["speaker_map"] = dict(data.get("speaker_map") or {})
            data["speaker_map_schema_version"] = 1
            data["speaker_map_provenance"] = _sidecar_provenance(method)
            data.setdefault("speaker_id_to_db_id", {})

        self._mutate_sidecar(transcript_path, mutator)
        return self.get_mapping(transcript_path)

    def unignore_speaker(
        self,
        transcript_path: str,
        diarized_id: str,
        *,
        method: str = "web",
    ) -> SpeakerMapState:
        """Remove diarized ID from ignored_speakers list."""
        did = normalize_diarized_id(diarized_id)
        path = Path(transcript_path)
        if not path.exists():
            raise FileNotFoundError(transcript_path)

        def mutator(data: Dict[str, Any]) -> None:
            ignored = [
                normalize_diarized_id(s) for s in data.get("ignored_speakers") or []
            ]
            data["ignored_speakers"] = [s for s in ignored if s and s != did]
            data["speaker_map"] = dict(data.get("speaker_map") or {})
            data["speaker_map_schema_version"] = 1
            data["speaker_map_provenance"] = _sidecar_provenance(method)
            data.setdefault("speaker_id_to_db_id", {})

        self._mutate_sidecar(transcript_path, mutator)
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
        """Replace mapping and ignored list in the sidecar."""
        path = Path(transcript_path)
        if not path.exists():
            raise FileNotFoundError(transcript_path)
        normalized_map = {
            normalize_diarized_id(k): normalize_display_name(v)
            for k, v in speaker_map.items()
            if normalize_diarized_id(k)
        }
        normalized_ignored = [
            normalize_diarized_id(s) for s in (ignored_speakers or [])
        ]

        def mutator(data: Dict[str, Any]) -> None:
            data["speaker_map"] = normalized_map
            data["ignored_speakers"] = list(
                dict.fromkeys([s for s in normalized_ignored if s])
            )
            data["speaker_map_schema_version"] = 1
            data["speaker_map_provenance"] = _sidecar_provenance(method)
            data["speaker_id_to_db_id"] = {
                normalize_diarized_id(k): int(v)
                for k, v in (
                    speaker_id_to_db_id or data.get("speaker_id_to_db_id") or {}
                ).items()
                if normalize_diarized_id(k)
            }
            if speaker_map_source is not None:
                data["speaker_map_source"] = speaker_map_source

        self._mutate_sidecar(transcript_path, mutator)
        return self.get_mapping(transcript_path)
