"""Find and delete transcripts linked to a source audio file.

Used after merge when the operator asks to remove original parts: same-stem
library JSON plus processing-state links, including speaker-map and import
sidecars. Analysis output folders are left in place.
"""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.audio.types import SUPPORTED_AUDIO_EXTENSIONS
from transcriptx.core.utils._path_core import get_canonical_base_name
from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import (
    DIARISED_TRANSCRIPTS_DIR,
    READABLE_TRANSCRIPTS_DIR,
    TRANSCRIPTS_ORIGINALS_DIR,
)
from transcriptx.core.utils.processing_state import (
    load_processing_state,
    save_processing_state,
)
from transcriptx.io.import_metadata.paths import (
    legacy_flat_sidecar_path_for_transcript,
    mirrored_import_sidecar_path_for_transcript,
)
from transcriptx.io.speaker_map_resolver import speaker_map_sidecar_candidates

logger = get_logger()

_AUDIO_SUFFIXES = SUPPORTED_AUDIO_EXTENSIONS
_AUDIO_STATE_FIELDS = (
    "audio_path",
    "mp3_path",
    "wav_path",
    "original_audio_path",
    "source_audio_path",
)
_TRANSCRIPT_STATE_FIELDS = (
    "transcript_path",
    "current_transcript_path",
    "original_transcript_path",
)
_STEM_TRANSCRIPT_SUFFIXES = (
    ".json",
    "_transcript_diarised.json",
    "_transcriptx.json",
)


def _resolve(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path


def _same_file(left: Path, right: Path) -> bool:
    return _resolve(left) == _resolve(right)


def _is_managed_transcript(path: Path) -> bool:
    try:
        _resolve(path).relative_to(_resolve(Path(DIARISED_TRANSCRIPTS_DIR)))
        return True
    except ValueError:
        return False


def _entry_audio_candidates(key: str, entry: dict) -> list[Path]:
    out: list[Path] = []
    raw_values = [key, *(entry.get(field) for field in _AUDIO_STATE_FIELDS)]
    for raw in raw_values:
        if not raw:
            continue
        path = Path(str(raw))
        if path.suffix.lower() in _AUDIO_SUFFIXES:
            out.append(path)
    return out


def _entry_transcript_path(entry: dict) -> Path | None:
    for field in _TRANSCRIPT_STATE_FIELDS:
        raw = entry.get(field)
        if raw:
            return Path(str(raw))
    return None


def find_transcripts_for_audio(audio_path: Path) -> list[Path]:
    """Return managed transcript JSON files linked to *audio_path*."""
    found: dict[str, Path] = {}

    def add(path: Path | None) -> None:
        if path is None or not path.is_file():
            return
        if not _is_managed_transcript(path):
            return
        found[str(_resolve(path))] = path

    state = load_processing_state(validate=False)
    processed = state.get("processed_files") or {}
    if isinstance(processed, dict):
        for key, entry in processed.items():
            if not isinstance(entry, dict):
                continue
            if any(
                _same_file(candidate, audio_path)
                for candidate in _entry_audio_candidates(str(key), entry)
            ):
                add(_entry_transcript_path(entry))

    stem = audio_path.stem
    root = Path(DIARISED_TRANSCRIPTS_DIR)
    if root.exists():
        for suffix in _STEM_TRANSCRIPT_SUFFIXES:
            add(root / f"{stem}{suffix}")
        for suffix in _STEM_TRANSCRIPT_SUFFIXES:
            pattern = f"{stem}{suffix}"
            for match in root.rglob(pattern):
                if match.name == pattern:
                    add(match)

    return list(found.values())


def companion_files_for_transcript(transcript: Path) -> list[Path]:
    """Transcript JSON plus speaker-map, import sidecar, readable, and original copies."""
    files: list[Path] = [transcript]
    seen = {str(_resolve(transcript))}

    def add(path: Path | None) -> None:
        if path is None or not path.is_file():
            return
        key = str(_resolve(path))
        if key in seen:
            return
        seen.add(key)
        files.append(path)

    for candidate in speaker_map_sidecar_candidates(transcript):
        add(candidate)
    add(mirrored_import_sidecar_path_for_transcript(transcript))
    add(legacy_flat_sidecar_path_for_transcript(transcript))

    stem = get_canonical_base_name(str(transcript))
    readable_root = Path(READABLE_TRANSCRIPTS_DIR)
    for ext in (".txt", ".md"):
        add(readable_root / f"{stem}{ext}")
    add(Path(TRANSCRIPTS_ORIGINALS_DIR) / transcript.name)
    return files


def _drop_processing_state_for_transcripts(transcripts: list[Path]) -> None:
    if not transcripts:
        return
    targets = {str(_resolve(path)) for path in transcripts}
    state = load_processing_state(validate=False)
    processed = state.get("processed_files") or {}
    if not isinstance(processed, dict) or not processed:
        return

    kept: dict = {}
    removed = 0
    for key, entry in processed.items():
        if not isinstance(entry, dict):
            kept[key] = entry
            continue
        linked = False
        for field in _TRANSCRIPT_STATE_FIELDS:
            raw = entry.get(field)
            if not raw:
                continue
            try:
                if str(Path(str(raw)).resolve()) in targets:
                    linked = True
                    break
            except OSError:
                if str(raw) in targets:
                    linked = True
                    break
        if linked:
            removed += 1
            continue
        kept[key] = entry

    if removed:
        state["processed_files"] = kept
        save_processing_state(state)
        logger.info(
            "Removed %s processing-state entries for deleted merge transcripts",
            removed,
        )


def drop_processing_state_for_transcripts(transcripts: list[Path]) -> None:
    """Remove processed_files entries that point at the given transcript paths."""
    _drop_processing_state_for_transcripts(transcripts)


def delete_linked_transcripts_for_audio(audio_path: Path) -> tuple[int, list[str]]:
    """Delete managed transcripts (and companions) linked to *audio_path*.

    Returns (transcript_json_count, warnings).
    """
    transcripts = find_transcripts_for_audio(audio_path)
    if not transcripts:
        return 0, []

    deleted = 0
    deleted_transcripts: list[Path] = []
    warnings: list[str] = []
    for transcript in transcripts:
        companions = companion_files_for_transcript(transcript)
        json_deleted = False
        for path in companions:
            try:
                path.unlink()
                if _same_file(path, transcript):
                    json_deleted = True
                    deleted += 1
                logger.info("Deleted merge-linked transcript artifact: %s", path)
            except OSError as exc:
                warnings.append(f"Could not delete transcript file {path.name}: {exc}")
        if json_deleted:
            deleted_transcripts.append(transcript)

    _drop_processing_state_for_transcripts(deleted_transcripts)
    return deleted, warnings
