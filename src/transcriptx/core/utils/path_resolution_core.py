"""
Shared path resolution helpers used by PathResolver strategies.

Single implementation of state lookup, canonical/suffix/heuristic matching.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from transcriptx.core.utils import paths as paths_module
from transcriptx.core.utils._path_core import (
    get_canonical_base_name,
    strip_duplicate_filename_suffix,
)


def _path_dir(value: str | Path) -> Path:
    """Coerce config dir (str or Path) for joins; tests monkeypatch with str."""
    return Path(value)


def validate_resolved_file_type(file_path: Path, file_type: str) -> bool:
    """Return True if path matches expected file_type for resolution."""
    suffix_lower = file_path.suffix.lower()

    if file_type == "audio":
        audio_extensions = {
            ".mp3",
            ".wav",
            ".m4a",
            ".flac",
            ".aac",
            ".ogg",
            ".opus",
            ".mp4",
            ".m4v",
            ".webm",
        }
        return suffix_lower in audio_extensions
    if file_type == "transcript":
        return suffix_lower == ".json"
    if file_type == "output_dir":
        return file_path.is_dir()
    if file_type == "speaker_map":
        return suffix_lower == ".json"
    return True


def find_state_entry_by_path(
    file_path: str, processed_files: Dict[str, Any]
) -> Optional[tuple]:
    """Find entry in processed_files by searching transcript_path fields."""
    file_base = get_canonical_base_name(file_path)

    for key, metadata in processed_files.items():
        entry_transcript_path = metadata.get("transcript_path", "")
        transcribe_step = metadata.get("transcribe", {})
        if not transcribe_step:
            steps = metadata.get("steps", {})
            transcribe_step = steps.get("transcribe", {})
        step_transcript_path = transcribe_step.get("transcript_path", "")

        entry_canonical_base = metadata.get("canonical_base_name", "")
        if entry_canonical_base and file_base:
            if entry_canonical_base == file_base:
                return (key, metadata)
            if entry_canonical_base == strip_duplicate_filename_suffix(file_base):
                return (key, metadata)

        if entry_transcript_path == file_path or step_transcript_path == file_path:
            return (key, metadata)

        if entry_transcript_path:
            variant_base = get_canonical_base_name(entry_transcript_path)
            if variant_base == file_base:
                return (key, metadata)

        if step_transcript_path:
            step_base = get_canonical_base_name(step_transcript_path)
            if step_base == file_base:
                return (key, metadata)
            if "_" in step_base:
                step_base_without_suffix = step_base.split("_")[0]
                if step_base_without_suffix == file_base:
                    return (key, metadata)

        entry_filename = (
            Path(entry_transcript_path).name if entry_transcript_path else ""
        )
        step_filename = Path(step_transcript_path).name if step_transcript_path else ""
        file_filename = Path(file_path).name

        if entry_transcript_path and entry_filename == file_filename:
            return (key, metadata)
        if step_transcript_path and step_filename == file_filename:
            return (key, metadata)

    return None


def get_path_from_state(
    file_path: str, file_type: str, validate: bool = True
) -> Optional[str]:
    """Get path from processing state with optional validation."""
    try:
        from transcriptx.core.utils.state_schema import validate_state_paths

        state_file = _path_dir(paths_module.PROCESSING_STATE_FILE)
        if not state_file.exists():
            return None

        with open(state_file, "r") as f:
            state = json.load(f)

        processed_files = state.get("processed_files", {})
        found = find_state_entry_by_path(file_path, processed_files)
        if not found:
            return None

        _key, metadata = found

        if validate:
            is_valid, errors = validate_state_paths(metadata)
            if not is_valid and file_type == "transcript":
                transcript_errors = [
                    e
                    for e in errors
                    if "transcript_path" in e.lower() or "transcript" in e.lower()
                ]
                if transcript_errors:
                    return None
            elif not is_valid:
                return None

        if file_type == "transcript":
            path = metadata.get("transcript_path")
            if path and Path(path).exists():
                return path
            transcribe_step = metadata.get("transcribe", {})
            if not transcribe_step:
                steps = metadata.get("steps", {})
                transcribe_step = steps.get("transcribe", {})
            step_path = transcribe_step.get("transcript_path", "")
            if step_path and Path(step_path).exists():
                return step_path
            return path
        if file_type == "audio":
            return metadata.get("mp3_path")
        if file_type == "output_dir":
            return metadata.get("output_dir_path")

        return None
    except Exception:
        pass

    return None


def try_canonical_base_match(canonical_base: str, file_type: str) -> Optional[str]:
    """Try to find file using canonical base name."""
    diarised = _path_dir(paths_module.DIARISED_TRANSCRIPTS_DIR)
    outputs = _path_dir(paths_module.OUTPUTS_DIR)
    recordings = _path_dir(paths_module.RECORDINGS_DIR)

    if file_type == "transcript":
        path = diarised / f"{canonical_base}.json"
        if path.exists():
            return str(path.resolve())

        if diarised.exists():
            for json_file in diarised.rglob(f"{canonical_base}.json"):
                if json_file.exists():
                    return str(json_file.resolve())

        if outputs.exists():
            for json_file in outputs.rglob(f"{canonical_base}.json"):
                if json_file.exists():
                    return str(json_file.resolve())

    elif file_type == "audio":
        if recordings.exists():
            audio_exts = [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"]
            bases_to_try = [canonical_base]
            stripped = strip_duplicate_filename_suffix(canonical_base)
            if stripped != canonical_base:
                bases_to_try.append(stripped)
            for base in bases_to_try:
                for ext in audio_exts:
                    audio_file = recordings / f"{base}{ext}"
                    if audio_file.exists():
                        return str(audio_file.resolve())

    elif file_type == "output_dir":
        output_dir = outputs / canonical_base
        if output_dir.exists():
            return str(output_dir.resolve())

    return None


def try_suffix_variants(
    base_name: str, canonical_base: str, file_type: str
) -> Optional[str]:
    """Try to find file using suffix variants."""
    if base_name != canonical_base:
        return try_canonical_base_match(base_name, file_type)
    return None


def heuristic_search(
    file_path: str, file_type: str, base_name: Optional[str] = None
) -> Optional[str]:
    """Heuristic search with early exit and pattern matching."""
    if base_name is None:
        base_name = get_canonical_base_name(file_path)

    if file_type == "transcript":
        try:
            state_file = _path_dir(paths_module.PROCESSING_STATE_FILE)
            if state_file.exists():
                with open(state_file, "r") as f:
                    state = json.load(f)

                processed_files = state.get("processed_files", {})
                for _audio_path, metadata in processed_files.items():
                    entry_transcript_path = metadata.get("transcript_path", "")
                    transcribe_step = metadata.get("transcribe", {})
                    if not transcribe_step:
                        steps = metadata.get("steps", {})
                        transcribe_step = steps.get("transcribe", {})
                    step_transcript_path = transcribe_step.get("transcript_path", "")

                    for variant_path in [entry_transcript_path, step_transcript_path]:
                        if not variant_path:
                            continue

                        variant_base = get_canonical_base_name(variant_path)
                        if variant_base == base_name or (
                            Path(variant_path).exists()
                            and get_canonical_base_name(variant_path) == base_name
                        ):
                            if Path(variant_path).exists():
                                return str(Path(variant_path).resolve())
        except Exception:
            pass

    if file_type == "transcript":
        search_dirs = [
            _path_dir(paths_module.DIARISED_TRANSCRIPTS_DIR),
            _path_dir(paths_module.OUTPUTS_DIR),
        ]
        patterns = [f"{base_name}.json", f"{base_name}_*.json"]
    else:
        search_dirs = [_path_dir(paths_module.OUTPUTS_DIR)]
        patterns = [f"{base_name}.*"]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        for pattern in patterns:
            if "*" not in pattern:
                candidate = search_dir / pattern
                if candidate.exists():
                    return str(candidate.resolve())

            matches = list(search_dir.glob(pattern))
            if matches:
                for match in matches:
                    if match.exists():
                        if base_name in str(match.parent):
                            return str(match.resolve())

                return str(matches[0].resolve())

    path_obj = Path(file_path)
    if file_type == "transcript" and path_obj.exists():
        try:
            file_stat = path_obj.stat()
            file_size = file_stat.st_size
            file_mtime = file_stat.st_mtime
        except OSError:
            return None

        outputs = _path_dir(paths_module.OUTPUTS_DIR)
        if not outputs.exists():
            return None

        json_files = list(outputs.rglob("*.json"))[:100]
        for json_file in json_files:
            if json_file.name.endswith("_speaker_map.json"):
                continue
            try:
                json_stat = json_file.stat()
                size_diff = abs(json_stat.st_size - file_size) / max(file_size, 1)
                time_diff = abs(json_stat.st_mtime - file_mtime)

                if size_diff < 0.1 and time_diff < 7200:
                    return str(json_file.resolve())
            except (OSError, ValueError):
                continue

    return None
