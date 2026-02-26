"""
Path resolution logic for TranscriptX.

This module handles complex file path resolution with caching and heuristics,
including finding files after renaming and handling various naming patterns.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, Literal

from transcriptx.core.utils.paths import (
    OUTPUTS_DIR,
    DATA_DIR,
    DIARISED_TRANSCRIPTS_DIR,
    RECORDINGS_DIR,
)
from transcriptx.core.utils._path_core import get_canonical_base_name, get_base_name
from transcriptx.core.utils._path_cache import (
    _get_cache,
    _get_cache_ttl,
    _get_cache_stats_dict,
    _manage_cache_size,
)


def _validate_file_type(file_path: Path, file_type: str) -> bool:
    """
    Validate that a file path matches the expected file type.

    Args:
        file_path: Path to validate
    file_type: Expected file type ("transcript", "audio", "output_dir")

    Returns:
        True if file type matches, False otherwise
    """
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
    elif file_type == "transcript":
        return suffix_lower == ".json"
    elif file_type == "output_dir":
        return file_path.is_dir()

    # Unknown file type - accept any file
    return True


def resolve_file_path(
    file_path: str,
    file_type: Literal["transcript", "audio", "output_dir"] = "transcript",
    validate_state: bool = True,
    use_cache: bool = True,
    use_new_resolver: bool = False,
) -> str:
    """
    Unified path resolution with consistent strategy order and caching.

    This function consolidates path resolution logic from multiple places,
    providing a single, reliable way to find files even after renaming.

    Strategy order:
    1. Cache lookup (if enabled and valid)
    2. Processing state lookup (with validation if enabled)
    3. Exact path match
    4. Canonical base name match
    5. Suffix variant matching
    6. Heuristic search (for transcripts, cached)

    Args:
        file_path: Original or expected file path
        file_type: Type of file to resolve
            - "transcript": Transcript JSON file
            - "audio": Audio file (MP3, WAV, etc.)
            - "output_dir": Output directory
        validate_state: Whether to validate state paths exist before using them
        use_cache: Whether to use cached results (default: True)
        use_new_resolver: Whether to use the new PathResolver (default: False, for migration)

    Returns:
        Resolved path to existing file or directory

    Raises:
        FileNotFoundError: If file cannot be found using any strategy
    """
    # Option to use new resolver (for gradual migration)
    if use_new_resolver:
        try:
            from transcriptx.core.utils.path_resolver import get_default_resolver

            resolver = get_default_resolver()
            return resolver.resolve(file_path, file_type, validate_state)
        except ImportError:
            # Fall back to old implementation if new resolver not available
            pass
    _path_resolution_cache = _get_cache()
    _cache_ttl = _get_cache_ttl()
    _cache_stats = _get_cache_stats_dict()

    # Check cache first (only for heuristic searches which are expensive)
    cache_key = (file_path, file_type)
    if cache_key in _path_resolution_cache and use_cache:
        cached_result, cached_time = _path_resolution_cache[cache_key]
        if time.time() - cached_time < _cache_ttl:
            # Validate cached result still exists
            if Path(cached_result).exists():
                _cache_stats["hits"] += 1
                return cached_result
            else:
                # Cached path no longer exists, remove from cache
                _path_resolution_cache.pop(cache_key, None)
                _cache_stats["misses"] += 1
    elif use_cache:
        _cache_stats["misses"] += 1

    path_obj = Path(file_path)

    # Strategy 1: Processing state lookup (with validation)
    if validate_state:
        state_path = _get_path_from_state(file_path, file_type, validate=True)
        if state_path:
            return str(Path(state_path).resolve())

    # Strategy 2: Exact path match (only if file type matches)
    if path_obj.exists():
        # Validate that the file type matches what was requested
        if _validate_file_type(path_obj, file_type):
            return str(path_obj.resolve())
        # If file exists but type doesn't match, don't return it (continue to other strategies)

    # Strategy 3: Canonical base name match
    canonical_base = get_canonical_base_name(file_path)
    resolved = _try_canonical_base_match(canonical_base, file_type)
    if resolved:
        return resolved

    # Strategy 4: Suffix variant matching
    base_name = get_base_name(file_path)
    if base_name != canonical_base:
        resolved = _try_suffix_variants(base_name, canonical_base, file_type)
        if resolved:
            return resolved

    # Strategy 5: Heuristic search (for transcripts and speaker maps)
    if file_type == "transcript":
        resolved = _heuristic_search(file_path, file_type, canonical_base)
        if resolved:
            # Cache heuristic search results (they're expensive)
            if use_cache:
                _path_resolution_cache[cache_key] = (resolved, time.time())
                _manage_cache_size()  # Ensure cache doesn't grow too large
            return resolved

    # All strategies failed
    raise FileNotFoundError(
        f"{file_type.replace('_', ' ').title()} not found: {file_path}. "
        f"Searched using multiple strategies."
    )


def _find_entry_by_path(
    file_path: str, processed_files: Dict[str, Any]
) -> Optional[tuple]:
    """
    Find entry in processed_files by searching transcript_path fields.

    This is a backward compatibility helper for path-based lookups.
    Returns (uuid_or_key, entry) tuple if found.

    Args:
        file_path: Path to search for
        processed_files: Dictionary of processed files

    Returns:
        Tuple of (key, entry) or None if not found
    """
    file_base = get_canonical_base_name(file_path)

    for key, metadata in processed_files.items():
        # Get all possible transcript paths from this entry
        entry_transcript_path = metadata.get("transcript_path", "")
        # Check both structures: metadata["transcribe"] and metadata["steps"]["transcribe"]
        transcribe_step = metadata.get("transcribe", {})
        if not transcribe_step:
            steps = metadata.get("steps", {})
            transcribe_step = steps.get("transcribe", {})
        step_transcript_path = transcribe_step.get("transcript_path", "")

        # Check canonical_base_name field
        entry_canonical_base = metadata.get("canonical_base_name", "")
        if entry_canonical_base and file_base and entry_canonical_base == file_base:
            return (key, metadata)

        # Check exact path matches
        if entry_transcript_path == file_path or step_transcript_path == file_path:
            return (key, metadata)

        # Check base name matches
        if entry_transcript_path:
            variant_base = get_canonical_base_name(entry_transcript_path)
            if variant_base == file_base:
                return (key, metadata)

        if step_transcript_path:
            step_base = get_canonical_base_name(step_transcript_path)
            if step_base == file_base:
                return (key, metadata)
            # Check if step path has suffix
            if "_" in step_base:
                step_base_without_suffix = step_base.split("_")[0]
                if step_base_without_suffix == file_base:
                    return (key, metadata)

        # Check filename matches
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


def _get_path_from_state(
    file_path: str, file_type: str, validate: bool = True
) -> Optional[str]:
    """Get path from processing state with optional validation."""
    try:
        from transcriptx.core.utils.state_schema import validate_state_paths

        processing_state_file = Path(DATA_DIR) / "processing_state.json"
        if not processing_state_file.exists():
            return None

        with open(processing_state_file, "r") as f:
            state = json.load(f)

        processed_files = state.get("processed_files", {})

        # Try to find entry by path (backward compatibility)
        found = _find_entry_by_path(file_path, processed_files)
        if not found:
            return None

        key, metadata = found

        # Validate if requested
        # Note: We don't fail validation for missing output_dir paths
        # when resolving transcript paths, as these may have been renamed
        if validate:
            is_valid, errors = validate_state_paths(metadata)
            # Only fail validation if the transcript_path itself is missing or invalid
            # Don't fail for missing output_dir (it may have been renamed)
            if not is_valid and file_type == "transcript":
                # Check if the error is only about output_dir
                transcript_errors = [
                    e
                    for e in errors
                    if "transcript_path" in e.lower() or "transcript" in e.lower()
                ]
                if transcript_errors:
                    # Real transcript path issue, fail
                    return None
                # Otherwise, continue - output_dir issues are OK for renamed files
            elif not is_valid:
                # For non-transcript file types, fail on any validation error
                return None

        # Return appropriate path based on file type
        if file_type == "transcript":
            # Prefer main transcript_path (it's more up-to-date after renaming)
            path = metadata.get("transcript_path")
            if path and Path(path).exists():
                return path
            # Fallback to step path if main path doesn't exist
            # Check both structures: metadata["transcribe"] and metadata["steps"]["transcribe"]
            transcribe_step = metadata.get("transcribe", {})
            if not transcribe_step:
                steps = metadata.get("steps", {})
                transcribe_step = steps.get("transcribe", {})
            step_path = transcribe_step.get("transcript_path", "")
            if step_path and Path(step_path).exists():
                return step_path
            # Return main path even if it doesn't exist (caller will handle)
            return path
        elif file_type == "audio":
            return metadata.get("mp3_path")
        elif file_type == "output_dir":
            return metadata.get("output_dir_path")

        return None
    except Exception:
        pass  # If state file doesn't exist or is invalid, continue

    return None


def _try_canonical_base_match(canonical_base: str, file_type: str) -> Optional[str]:
    """Try to find file using canonical base name."""
    if file_type == "transcript":
        # Try in DIARISED_TRANSCRIPTS_DIR
        path = Path(DIARISED_TRANSCRIPTS_DIR) / f"{canonical_base}.json"
        if path.exists():
            return str(path.resolve())

        # Try in OUTPUTS_DIR
        outputs_dir = Path(OUTPUTS_DIR)
        if outputs_dir.exists():
            for json_file in outputs_dir.rglob(f"{canonical_base}.json"):
                if json_file.exists():
                    return str(json_file.resolve())

    elif file_type == "audio":
        # Try in recordings directory
        recordings_dir = Path(RECORDINGS_DIR)
        if recordings_dir.exists():
            for ext in [".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"]:
                audio_file = recordings_dir / f"{canonical_base}{ext}"
                if audio_file.exists():
                    return str(audio_file.resolve())

    elif file_type == "output_dir":
        output_dir = Path(OUTPUTS_DIR) / canonical_base
        if output_dir.exists():
            return str(output_dir.resolve())

    return None


def _try_suffix_variants(
    base_name: str, canonical_base: str, file_type: str
) -> Optional[str]:
    """Try to find file using suffix variants."""
    # Already tried canonical base, now try with original base name
    if base_name != canonical_base:
        return _try_canonical_base_match(base_name, file_type)
    return None


def _heuristic_search(
    file_path: str, file_type: str, base_name: Optional[str] = None
) -> Optional[str]:
    """
    Optimized heuristic search with early exit and pattern matching.

    Args:
        file_path: Original file path
        file_type: Type of file to find
        base_name: Canonical base name (if available)

    Returns:
        Resolved path if found, None otherwise
    """
    # Use base_name if available, otherwise extract from file_path
    if base_name is None:
        base_name = get_canonical_base_name(file_path)

    # First, try to find matching entry in processing state by checking all transcript paths
    # This handles cases where files were renamed (e.g., 20251225192953 -> 251225_test)
    if file_type == "transcript":
        try:
            processing_state_file = Path(DATA_DIR) / "processing_state.json"
            if processing_state_file.exists():
                with open(processing_state_file, "r") as f:
                    state = json.load(f)

                processed_files = state.get("processed_files", {})
                for audio_path, metadata in processed_files.items():
                    # Check all transcript path variants in this entry
                    entry_transcript_path = metadata.get("transcript_path", "")
                    # Check both structures: metadata["transcribe"] and metadata["steps"]["transcribe"]
                    transcribe_step = metadata.get("transcribe", {})
                    if not transcribe_step:
                        steps = metadata.get("steps", {})
                        transcribe_step = steps.get("transcribe", {})
                    step_transcript_path = transcribe_step.get("transcript_path", "")

                    # Check if the requested path matches any variant in this entry
                    for variant_path in [entry_transcript_path, step_transcript_path]:
                        if not variant_path:
                            continue

                        variant_base = get_canonical_base_name(variant_path)
                        # If canonical bases match, or if the variant path exists and matches the file we're looking for
                        if variant_base == base_name or (
                            Path(variant_path).exists()
                            and get_canonical_base_name(variant_path) == base_name
                        ):
                            # Found a match in state - check if the file exists
                            if Path(variant_path).exists():
                                return str(Path(variant_path).resolve())
        except Exception:
            pass  # If state lookup fails, continue with file system search

    # Determine search directories and patterns based on file type
    if file_type == "transcript":
        search_dirs = [Path(DIARISED_TRANSCRIPTS_DIR), Path(OUTPUTS_DIR)]
        patterns = [f"{base_name}.json", f"{base_name}_*.json"]
    else:
        search_dirs = [Path(OUTPUTS_DIR)]
        patterns = [f"{base_name}.*"]

    # Search with early exit - try most specific patterns first
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        for pattern in patterns:
            # Use glob with limit to avoid full directory traversal
            # Try exact match first (fastest)
            if "*" not in pattern:
                candidate = search_dir / pattern
                if candidate.exists():
                    return str(candidate.resolve())

            # Use glob for patterns with wildcards
            matches = list(search_dir.glob(pattern))
            if matches:
                # Return first match (most likely correct)
                # Prefer files in subdirectories matching base_name
                for match in matches:
                    if match.exists():
                        # Prefer matches in directories named after base_name
                        if base_name in str(match.parent):
                            return str(match.resolve())

                # Fallback to first match
                return str(matches[0].resolve())

    # If pattern matching failed, fall back to metadata-based search
    # (only for transcripts, and only if file_path exists)
    path_obj = Path(file_path)
    if file_type == "transcript" and path_obj.exists():
        try:
            file_stat = path_obj.stat()
            file_size = file_stat.st_size
            file_mtime = file_stat.st_mtime
        except OSError:
            return None

        outputs_dir = Path(OUTPUTS_DIR)
        if not outputs_dir.exists():
            return None

        if file_type == "transcript":
            # Search for JSON files with similar size and mtime (limited search)
            # Limit to first 100 files to avoid full traversal
            json_files = list(outputs_dir.rglob("*.json"))[:100]
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
