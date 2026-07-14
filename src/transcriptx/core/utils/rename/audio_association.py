"""Audio association kinds and recordings-root containment for managed rename."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from transcriptx.core.utils._path_core import (
    get_base_name,
    strip_duplicate_filename_suffix,
)
from transcriptx.core.utils._path_resolution import resolve_file_path
from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import (
    OUTPUTS_DIR,
    PATHS,
    PROCESSING_STATE_FILE,
    RECORDINGS_DIR,
    TRANSCRIPTS_ORIGINALS_DIR,
)

logger = get_logger()

_AUDIO_EXTENSIONS = (".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg")


class AudioAssociationKind(str, Enum):
    recordings_working_copy = "recordings_working_copy"
    archival_original = "archival_original"
    external_or_unknown = "external_or_unknown"
    missing = "missing"
    none = "none"


@dataclass(frozen=True)
class AudioAssociation:
    kind: AudioAssociationKind
    path: Path | None = None
    renameable: bool = False
    warning: str = ""


def approved_recordings_roots() -> tuple[Path, ...]:
    return (Path(RECORDINGS_DIR), Path(OUTPUTS_DIR) / "recordings")


def archival_roots() -> tuple[Path, ...]:
    return (Path(TRANSCRIPTS_ORIGINALS_DIR), Path(PATHS.wav_backup_dir))


def _is_under(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
    except OSError:
        return False
    try:
        resolved.relative_to(root_resolved)
        return True
    except ValueError:
        return False


def classify_audio_path(path: Path | None) -> AudioAssociation:
    """Classify a candidate audio path for rename eligibility."""
    if path is None:
        return AudioAssociation(kind=AudioAssociationKind.none, renameable=False)
    if not path.exists():
        return AudioAssociation(
            kind=AudioAssociationKind.missing,
            path=path,
            renameable=False,
            warning=f"Linked audio missing: {path}",
        )
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path

    for root in archival_roots():
        if root.exists() and _is_under(resolved, root):
            return AudioAssociation(
                kind=AudioAssociationKind.archival_original,
                path=resolved,
                renameable=False,
                warning="Archival/original audio is stable and will not be renamed",
            )

    for root in approved_recordings_roots():
        if _is_under(resolved, root):
            return AudioAssociation(
                kind=AudioAssociationKind.recordings_working_copy,
                path=resolved,
                renameable=True,
            )

    return AudioAssociation(
        kind=AudioAssociationKind.external_or_unknown,
        path=resolved,
        renameable=False,
        warning=f"External/unknown audio association preserved unchanged: {resolved}",
    )


def resolve_audio_association(
    transcript_path: str | Path,
    *,
    state_snapshot: dict | None = None,
) -> AudioAssociation:
    """Resolve linked audio and classify rename eligibility (never uses archival as renameable)."""
    found = find_original_audio_file(
        str(transcript_path), state_snapshot=state_snapshot
    )
    if found is None:
        return AudioAssociation(kind=AudioAssociationKind.none, renameable=False)
    return classify_audio_path(found)


def looks_like_uuid(key: str) -> bool:
    if not key or len(key) != 36:
        return False
    parts = key.split("-")
    return (
        len(parts) == 5
        and len(parts[0]) == 8
        and len(parts[1]) == 4
        and len(parts[2]) == 4
        and len(parts[3]) == 4
        and len(parts[4]) == 12
        and all(p.isalnum() for p in parts)
    )


def _audio_lookup_bases(*parts: Optional[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        for b in (p, strip_duplicate_filename_suffix(p)):
            if b and b not in seen:
                seen.add(b)
                out.append(b)
    return out


def _build_audio_candidates_from_recordings(
    bases_sequence: list[str],
    recordings_dirs: tuple[Path, ...],
    audio_extensions: tuple[str, ...],
) -> list[str]:
    out: list[str] = []

    def _add(raw: str | Path | None) -> None:
        if raw is None:
            return
        s = str(Path(raw))
        if s and s not in out:
            out.append(s)

    for base in bases_sequence:
        for dir_path in recordings_dirs:
            for ext in audio_extensions:
                _add(dir_path / f"{base}{ext}")
    return out


def ordered_audio_candidate_paths_for_state_entry(
    file_key: str,
    metadata: dict,
    transcript_path: str,
    *,
    resolved_audio_from_transcript: Optional[str],
    transcript_base: str,
    canonical_base_from_metadata: str,
    base_without_suffix: str,
    recordings_dirs: tuple[Path, ...],
    audio_extensions: tuple[str, ...],
) -> list[str]:
    out: list[str] = []

    def _add(raw: str | Path | None) -> None:
        if raw is None:
            return
        s = str(Path(raw))
        if s and s not in out:
            out.append(s)

    if metadata.get("audio_path"):
        _add(metadata["audio_path"])
    if not looks_like_uuid(file_key):
        _add(file_key)
    if metadata.get("mp3_path"):
        _add(metadata["mp3_path"])
    convert_step = metadata.get("convert", {})
    if isinstance(convert_step, dict):
        step_mp3 = convert_step.get("mp3_path")
        if step_mp3:
            _add(step_mp3)
    steps = metadata.get("steps", {})
    if isinstance(steps, dict):
        legacy_convert = steps.get("convert", {})
        if isinstance(legacy_convert, dict):
            legacy_step_mp3 = legacy_convert.get("mp3_path")
            if legacy_step_mp3:
                _add(legacy_step_mp3)
    if resolved_audio_from_transcript:
        _add(resolved_audio_from_transcript)
    for s in _build_audio_candidates_from_recordings(
        _audio_lookup_bases(
            canonical_base_from_metadata, transcript_base, base_without_suffix
        ),
        recordings_dirs,
        audio_extensions,
    ):
        _add(s)
    return out


def _fallback_audio_candidate_paths_no_state(
    transcript_path: str,
    *,
    resolved_full: Optional[str],
    resolved_stripped: Optional[str],
    transcript_base: str,
    base_without_suffix: str,
    recordings_dirs: tuple[Path, ...],
    audio_extensions: tuple[str, ...],
) -> list[str]:
    out: list[str] = []

    def _add(raw: str | Path | None) -> None:
        if raw is None:
            return
        s = str(Path(raw))
        if s and s not in out:
            out.append(s)

    if resolved_full:
        _add(resolved_full)
    if resolved_stripped:
        _add(resolved_stripped)
    for s in _build_audio_candidates_from_recordings(
        _audio_lookup_bases(transcript_base, base_without_suffix),
        recordings_dirs,
        audio_extensions,
    ):
        _add(s)
    return out


def find_original_audio_file(
    transcript_path: str,
    *,
    state_snapshot: dict | None = None,
) -> Optional[Path]:
    """Find linked audio path for a transcript (lookup only; not rename eligibility)."""
    try:
        recordings_dirs_tpl = approved_recordings_roots()
        exts_tpl = _AUDIO_EXTENSIONS

        def _first_existing(candidates: list[str]) -> Optional[Path]:
            for s in candidates:
                p = Path(s)
                if p.exists():
                    return p
            return None

        state = state_snapshot
        if state is None and PROCESSING_STATE_FILE.exists():
            with open(PROCESSING_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

        if state:
            processed_files = state.get("processed_files", {})
            for file_key, metadata in processed_files.items():
                if not isinstance(metadata, dict):
                    continue
                if metadata.get("transcript_path") != transcript_path:
                    continue

                resolved_audio: Optional[str] = None
                try:
                    resolved_audio = str(
                        resolve_file_path(
                            transcript_path,
                            file_type="audio",
                            validate_state=False,
                        )
                    )
                except FileNotFoundError:
                    resolved_audio = None

                transcript_base = get_base_name(transcript_path)
                canonical_base = metadata.get("canonical_base_name") or transcript_base
                base_without_suffix = (
                    transcript_base.rsplit("_", 1)[0]
                    if "_" in transcript_base
                    else transcript_base
                )

                candidate_strings = ordered_audio_candidate_paths_for_state_entry(
                    str(file_key),
                    metadata,
                    transcript_path,
                    resolved_audio_from_transcript=resolved_audio,
                    transcript_base=transcript_base,
                    canonical_base_from_metadata=str(canonical_base),
                    base_without_suffix=base_without_suffix,
                    recordings_dirs=recordings_dirs_tpl,
                    audio_extensions=exts_tpl,
                )
                hit = _first_existing(candidate_strings)
                if hit is not None:
                    return hit

        transcript_base = get_base_name(transcript_path)
        base_without_suffix = (
            transcript_base.rsplit("_", 1)[0]
            if "_" in transcript_base
            else transcript_base
        )
        resolved_full: Optional[str] = None
        try:
            resolved_full = str(
                resolve_file_path(
                    transcript_path, file_type="audio", validate_state=False
                )
            )
        except FileNotFoundError:
            pass
        resolved_stripped: Optional[str] = None
        try:
            resolved_stripped = str(
                resolve_file_path(
                    base_without_suffix,
                    file_type="audio",
                    validate_state=False,
                )
            )
        except FileNotFoundError:
            pass

        fallback = _fallback_audio_candidate_paths_no_state(
            transcript_path,
            resolved_full=resolved_full,
            resolved_stripped=resolved_stripped,
            transcript_base=transcript_base,
            base_without_suffix=base_without_suffix,
            recordings_dirs=recordings_dirs_tpl,
            audio_extensions=exts_tpl,
        )
        return _first_existing(fallback)
    except Exception as e:
        log_error("FILE_RENAME", f"Error finding original audio file: {e}", exception=e)
        return None
