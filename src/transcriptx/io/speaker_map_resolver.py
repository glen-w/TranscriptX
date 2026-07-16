"""Resolver for sidecar-backed speaker mapping state."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from transcriptx.core.store import SidecarStore
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import (
    canonical_transcript_relpath,
    speaker_map_path_for_transcript,
)

logger = get_logger()


def sidecar_path_for(transcript_path: str | Path) -> Path:
    """Return the speaker-map sidecar path for a transcript.

    For managed library transcripts under PATHS.transcripts_dir, this returns
    the canonical metadata path under PATHS.transcripts_metadata_dir / \"speaker_maps\"
    with a \".speaker_map.json\" suffix, mirroring the transcript-relative path.

    For non-library or ad-hoc transcripts (outside PATHS.transcripts_dir), this
    falls back to a co-located "{stem}.speaker_map.json" beside the transcript.
    """
    path = Path(transcript_path)
    try:
        canonical_transcript_relpath(path)
    except ValueError:
        return path.with_name(f"{path.stem}.speaker_map.json")
    return speaker_map_path_for_transcript(path)


def speaker_map_sidecar_candidates(transcript_path: str | Path) -> list[Path]:
    """Return the preferred speaker-map sidecar path(s) for a transcript.

    For managed library transcripts, this yields the canonical metadata path.
    For non-library transcripts, this yields legacy co-located candidates:
    - {stem}.speaker_map.json
    - {base}.speaker_map.json when transcript is *_transcriptx.json
    - {get_canonical_base_name}.speaker_map.json when that differs from stem
    """
    path = Path(transcript_path)
    try:
        # Managed canonical transcript: only the canonical metadata path.
        canonical_transcript_relpath(path)
        return [speaker_map_path_for_transcript(path)]
    except ValueError:
        # Non-library transcript: preserve legacy neighbor candidate behavior.
        from transcriptx.core.utils._path_core import get_canonical_base_name

        stem = path.stem
        names: list[str] = []
        seen: set[str] = set()

        def push(filename: str) -> None:
            if filename not in seen:
                seen.add(filename)
                names.append(filename)

        push(f"{stem}.speaker_map.json")
        if stem.endswith("_transcriptx"):
            push(f"{stem[: -len('_transcriptx')]}.speaker_map.json")
        canonical = get_canonical_base_name(str(path))
        if canonical != stem:
            push(f"{canonical}.speaker_map.json")

        return [path.parent / n for n in names]


def normalize_diarized_id(value: Any) -> str:
    """Normalize diarized IDs to a stable string form."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    upper = text.upper()
    if upper.isdigit():
        return f"SPEAKER_{int(upper):02d}"
    if upper.startswith("SPEAKER_") and upper[8:].isdigit():
        return f"SPEAKER_{int(upper[8:]):02d}"
    return text


def normalize_display_name(value: Any) -> str:
    """Normalize display names to a trimmed string."""
    if value is None:
        return ""
    return str(value).strip()


def is_effective_speaker_name(diarized_id: Any, display_name: Any) -> bool:
    """
    True when display_name is non-empty and not just the diarized placeholder.

    We treat mappings like SPEAKER_00 -> SPEAKER_00 as still unnamed so UI
    progress and pipeline gating do not count placeholder self-maps as
    identified speakers.
    """
    name = normalize_display_name(display_name)
    if not name:
        return False
    did = normalize_diarized_id(diarized_id)
    if not did:
        return True
    return normalize_diarized_id(name) != did


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


@dataclass(frozen=True)
class SpeakerMapState:
    """Resolved speaker mapping facts for a transcript."""

    has_sidecar: bool
    speaker_map: Dict[str, str] = field(default_factory=dict)
    ignored_speakers: List[str] = field(default_factory=list)
    schema_version: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = None
    speaker_id_to_db_id: Dict[str, int] = field(default_factory=dict)
    speaker_map_source: Optional[Dict[str, Any]] = None

    @property
    def named_speaker_count(self) -> int:
        """Count mapped speaker IDs with a non-empty name, excluding ignored IDs."""
        ignored = set(self.ignored_speakers)
        return sum(
            1
            for speaker_id, display_name in self.speaker_map.items()
            if speaker_id not in ignored
            and is_effective_speaker_name(speaker_id, display_name)
        )

    @property
    def ignored_speaker_count(self) -> int:
        return len(self.ignored_speakers)

    @property
    def has_named_speakers(self) -> bool:
        return self.named_speaker_count > 0

    @property
    def is_unmapped(self) -> bool:
        return not self.has_sidecar or (
            not self.speaker_map and not self.ignored_speakers
        )


def resolve_speaker_display_label(
    speaker: Any,
    speaker_map: Dict[str, str] | SpeakerMapState | None,
) -> str:
    """
    Return the identified display name for a diarized speaker id when available.

    Falls back to the original speaker string when the map is missing, empty,
    or only has a placeholder self-map (e.g. SPEAKER_00 -> SPEAKER_00).
    """
    raw = "" if speaker is None else str(speaker).strip()
    if not raw:
        return ""
    if isinstance(speaker_map, SpeakerMapState):
        mapping = speaker_map.speaker_map
    else:
        mapping = speaker_map or {}
    if not mapping:
        return raw
    nid = normalize_diarized_id(raw)
    mapped = mapping.get(nid) if nid else None
    if mapped is None:
        mapped = mapping.get(raw)
    if mapped is not None and is_effective_speaker_name(nid or raw, mapped):
        return normalize_display_name(mapped)
    return raw


class SpeakerMapResolver:
    """Load and resolve speaker mapping state from sidecar files."""

    def __init__(self, store: Optional[SidecarStore] = None) -> None:
        self._store = store or SidecarStore()

    def load_mapping(self, transcript_path: str | Path) -> SpeakerMapState:
        """Load sidecar-backed mapping state for a transcript."""
        transcript_path = Path(transcript_path)
        raw = None
        sidecar_path: Path | None = None
        for candidate in speaker_map_sidecar_candidates(transcript_path):
            raw = self._store.read(candidate)
            if raw is not None:
                sidecar_path = candidate
                if candidate != sidecar_path_for(transcript_path):
                    logger.info(
                        "Loaded speaker map from alternate sidecar path: %s",
                        candidate,
                    )
                break
        if raw is None:
            return SpeakerMapState(has_sidecar=False)
        if not isinstance(raw, dict):
            raise ValueError(f"Sidecar at {sidecar_path} is not a JSON object")

        speaker_map_raw = raw.get("speaker_map") or {}
        if not isinstance(speaker_map_raw, dict):
            raise ValueError(
                f"Sidecar at {sidecar_path} has invalid speaker_map (expected object)"
            )
        ignored_raw = raw.get("ignored_speakers") or []
        if not isinstance(ignored_raw, list):
            raise ValueError(
                f"Sidecar at {sidecar_path} has invalid ignored_speakers (expected list)"
            )
        db_map_raw = raw.get("speaker_id_to_db_id") or {}
        if not isinstance(db_map_raw, dict):
            raise ValueError(
                f"Sidecar at {sidecar_path} has invalid speaker_id_to_db_id (expected object)"
            )

        normalized_map: Dict[str, str] = {}
        for speaker_id, display_name in speaker_map_raw.items():
            did = normalize_diarized_id(speaker_id)
            name = normalize_display_name(display_name)
            if did:
                normalized_map[did] = name

        normalized_ignored = _dedupe_preserve_order(
            normalize_diarized_id(s) for s in ignored_raw
        )
        normalized_db_map: Dict[str, int] = {}
        for speaker_id, db_id in db_map_raw.items():
            did = normalize_diarized_id(speaker_id)
            if not did:
                continue
            try:
                normalized_db_map[did] = int(db_id)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Sidecar at {sidecar_path} has invalid speaker_id_to_db_id value for {speaker_id!r}"
                ) from exc

        provenance = raw.get("speaker_map_provenance")
        if provenance is not None and not isinstance(provenance, dict):
            raise ValueError(
                f"Sidecar at {sidecar_path} has invalid speaker_map_provenance (expected object)"
            )
        speaker_map_source = raw.get("speaker_map_source")
        if speaker_map_source is not None and not isinstance(speaker_map_source, dict):
            raise ValueError(
                f"Sidecar at {sidecar_path} has invalid speaker_map_source (expected object)"
            )

        schema_version = raw.get("schema_version") or raw.get(
            "speaker_map_schema_version"
        )
        if schema_version is not None:
            schema_version = str(schema_version)

        return SpeakerMapState(
            has_sidecar=True,
            speaker_map=normalized_map,
            ignored_speakers=normalized_ignored,
            schema_version=schema_version,
            provenance=provenance,
            speaker_id_to_db_id=normalized_db_map,
            speaker_map_source=speaker_map_source,
        )

    def resolve_segments(
        self,
        segments: List[Dict[str, Any]],
        speaker_map: Dict[str, str] | SpeakerMapState | None,
    ) -> List[Dict[str, Any]]:
        """Return a new list with speakers resolved in memory."""
        if isinstance(speaker_map, SpeakerMapState):
            mapping = speaker_map.speaker_map
            db_map = speaker_map.speaker_id_to_db_id
        else:
            mapping = speaker_map or {}
            db_map = {}

        resolved: List[Dict[str, Any]] = []
        for segment in segments:
            if not isinstance(segment, dict):
                resolved.append(segment)
                continue
            copied = dict(segment)
            speaker = copied.get("speaker")
            if speaker is not None:
                normalized = normalize_diarized_id(speaker)
                if normalized in mapping:
                    copied["speaker"] = mapping[normalized]
                    db_id = db_map.get(normalized)
                    if db_id is not None:
                        copied["speaker_db_id"] = db_id
            resolved.append(copied)
        return resolved

    def has_named_speakers(self, transcript_path: str | Path) -> bool:
        """Convenience presence query used by policy/UI callers."""
        return self.load_mapping(transcript_path).has_named_speakers
