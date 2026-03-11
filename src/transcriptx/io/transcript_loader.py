"""
Transcript loading utilities for TranscriptX.

This module has **one clearly defined role per function**.  The two paths are
structurally separated in code, not just documented:

Canonical path (schema v1.0 artifacts)
---------------------------------------
``load_segments()`` → ``_load_segments_from_data()`` detects a v1.0 artifact
(``schema_version`` + ``source`` keys present) and returns ``data["segments"]``
directly.  No normalisation is needed: the importer already did that work.

Legacy compatibility path (raw / pre-import JSON)
--------------------------------------------------
When ``_load_segments_from_data()`` sees data that is *not* a v1.0 artifact
(bare segment list, raw WhisperX output, dict without ``schema_version``), it
delegates to ``_normalize_legacy_segments()``.  That function handles:

* Raw WhisperX segments — segments with a ``words`` array but no ``speaker``
  field; speaker is promoted from the most-common word-level speaker.
* Bare segment lists (``isinstance(data, list)``).
* Segments that have no resolvable speaker → ``"UNKNOWN_SPEAKER"``.

The legacy shim is kept because:
* Some raw JSON files on disk have never been re-imported through the adapter
  pipeline.
* A few callers pass raw WhisperX dicts already in memory.

``_normalize_legacy_segments`` is deliberately **not** called on v1.0 artifacts:
those are handled by the fast path above, keeping the two behaviours separate.

Public surface: ``load_segments()``, ``normalize_segments()``, ``load_transcript()``,
``load_transcript_data()``.  Everything else is internal.

Path resolution invariant (canonical)
--------------------------------------
All file-path resolution for transcripts is owned by this layer (and
_path_resolution). If the input path exists, it is used. If missing,
resolution is attempted via _path_resolution.resolve_file_path(path, file_type="transcript")
(e.g. renamed files after speaker mapping). If resolution fails, FileNotFoundError
is raised with the original path in the message. Callers outside the io layer
must not implement their own path-resolution fallback.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional


class TranscriptLoadResult(NamedTuple):
    """
    Result of loading transcript data (segments, paths, speaker map).

    Returned by TranscriptService.load_transcript_data and transcript_loader.load_transcript_data.
    Tuple-unpacking remains valid: segments, base_name, transcript_dir, speaker_map = load_transcript_data(...)
    """

    segments: List[Dict[str, Any]]
    base_name: str
    transcript_dir: str
    speaker_map: Dict[str, str]


# Avoid importing from transcriptx.core at top level to prevent circular import
# (core -> pipeline -> pipeline_context -> transcript_service -> transcript_loader).
# CanonicalTranscript is imported inside load_canonical_transcript().


def normalize_segments(data: Any) -> List[Dict[str, Any]]:
    """Extract and normalise segments from any transcript data structure (public API).

    Routes between the canonical v1.0 fast-path and the legacy compatibility
    shim.  Callers that already hold a parsed JSON dict or a raw segment list
    can pass it here without loading from a file.

    For new code, prefer calling ``load_segments(path)`` or passing a v1.0
    artifact dict — the legacy path exists only for backward compatibility.
    """
    return _load_segments_from_data(data)


def _load_segments_from_data(data: Any) -> List[Dict[str, Any]]:
    """Route segment extraction between the canonical path and the legacy path.

    * **v1.0 artifact** (dict with ``schema_version`` + ``source``): returns
      ``data["segments"]`` directly.  No normalisation is applied; the importer
      already did that work.

    * **Everything else** (raw WhisperX dict, bare list, pre-import JSON): delegates
      to ``_normalize_legacy_segments()``, the backward-compatibility shim.
    """
    if (
        isinstance(data, dict)
        and "schema_version" in data
        and "source" in data
    ):
        # Fast path: canonical schema v1.0 artifact.
        return data.get("segments", [])

    # Legacy path: raw or pre-import data.
    return _normalize_legacy_segments(data)


def _normalize_legacy_segments(data: Any) -> List[Dict[str, Any]]:
    """Backward-compatibility shim for raw / pre-import JSON.

    Handles three legacy shapes:

    1. ``{"segments": [...]}`` dict *without* ``schema_version`` (old-style exports).
    2. Bare ``list`` of segments (raw WhisperX output or similar).
    3. Segments that have a ``words`` array but no ``speaker`` field
       (raw WhisperX segments before speaker diarisation was merged in) — speaker
       is promoted from the most-common word-level speaker, falling back to
       ``"UNKNOWN_SPEAKER"`` when no word carries a speaker label.

    **Do not call this on v1.0 artifacts.**  ``_load_segments_from_data`` handles
    the routing; this function is only for data that has not gone through the
    adapter pipeline.
    """
    raw: List[Any] = []
    if isinstance(data, dict):
        raw = data.get("segments", [])
    elif isinstance(data, list):
        raw = data

    result: List[Dict[str, Any]] = []
    for segment in raw:
        if not isinstance(segment, dict):
            result.append(segment)
            continue

        # Raw WhisperX: segment has words array but no speaker field.
        if "words" in segment and "speaker" not in segment:
            words = segment.get("words") or []
            speaker_counts: Dict[str, int] = {}
            for word in words:
                if isinstance(word, dict) and "speaker" in word:
                    lbl = word["speaker"]
                    speaker_counts[lbl] = speaker_counts.get(lbl, 0) + 1

            promoted = segment.copy()
            if speaker_counts:
                promoted["speaker"] = max(speaker_counts, key=speaker_counts.get)
            else:
                promoted["speaker"] = "UNKNOWN_SPEAKER"
            result.append(promoted)
        else:
            result.append(segment)

    return result


def load_segments(path: str, data: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Load segments from a transcript JSON file or a pre-parsed dict.

    For schema v1.0 artifacts (produced by ``import_transcript()``), segments are
    returned as-is — no normalisation is applied.  For legacy / raw JSON the
    backward-compatibility shim (``_normalize_legacy_segments``) is invoked
    automatically.  See the module docstring for a full description of each path.

    Args:
        path: Path to the transcript JSON file.  Required even when *data* is
            provided (kept for API stability; not read when *data* is given).
        data: Optional pre-loaded transcript dict.  When provided the file is not
            read and *path* is used only for error messages.

    Returns:
        List of segment dicts.

    Raises:
        FileNotFoundError: File not found and path resolution fails.
        ValueError: Path is not a ``.json`` file.

    Note:
        Only ``.json`` files are accepted.  Any other source format must be
        converted first with ``transcript_importer.ensure_json_artifact(path)``.
    """
    if data is not None:
        return _load_segments_from_data(data)

    path_obj = Path(path)
    if path_obj.suffix.lower() != ".json":
        raise ValueError(
            f"load_segments() only accepts .json files, got: {path_obj.suffix!r}. "
            f"Convert the source file first with "
            f"transcript_importer.ensure_json_artifact(path)."
        )

    resolved_path = path
    if not path_obj.exists():
        try:
            from transcriptx.core.utils._path_resolution import resolve_file_path
            from transcriptx.core.utils.logger import get_logger

            resolved_path = resolve_file_path(path, file_type="transcript")
            get_logger().debug(f"Resolved transcript path: {path} -> {resolved_path}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Transcript file not found: {path}")

    with open(resolved_path) as f:
        file_data = json.load(f)

    return _load_segments_from_data(file_data)


def extract_speaker_map_from_transcript(transcript_path: str) -> Dict[str, str]:
    """
    Extract speaker map from transcript JSON metadata.

    This is a pure function that reads the transcript JSON and returns the
    speaker_map field if present. Returns empty dict if not found or on error.
    """
    try:
        with open(transcript_path, "r") as f:
            data = json.load(f)
        speaker_map = data.get("speaker_map", {})
        return speaker_map if isinstance(speaker_map, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def extract_ignored_speakers_from_transcript(transcript_path: str | Path) -> List[str]:
    """
    Extract ignored speaker IDs from transcript JSON metadata.

    Returns a unique, stable-order list of string IDs.
    """
    try:
        data = load_transcript(str(transcript_path))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, dict):
        return []
    raw_ids = data.get("ignored_speakers") or []
    if not isinstance(raw_ids, list):
        return []
    normalized = [str(item) for item in raw_ids if item is not None]
    return list(dict.fromkeys(normalized))


def load_canonical_transcript(path: str) -> "CanonicalTranscript":
    """
    Load a transcript file and return a CanonicalTranscript instance.

    This does not change behavior for existing callers; it simply wraps
    load_segments() into the canonical in-memory representation.
    """
    from transcriptx.core.domain.canonical_transcript import CanonicalTranscript

    segments = load_segments(path)
    if not segments:
        raise ValueError(f"No segments found in transcript: {path}")
    return CanonicalTranscript.from_segments(segments)


def load_transcript(path: str) -> Any:
    """
    Load a complete transcript file as JSON.

    This function loads the entire transcript file without any processing,
    useful when you need access to the full file structure including
    metadata, configuration, or other non-segment data. When the path
    does not exist, resolution is attempted (e.g. renamed files) so that
    path resolution is owned by the io layer only.

    Args:
        path: Path to the transcript JSON file

    Returns:
        The complete JSON data from the file

    Raises:
        FileNotFoundError: If the file does not exist and resolution fails.

    Note:
        Unlike load_segments(), this function preserves the complete
        file structure, including any metadata, configuration, or
        additional fields that might be present in the transcript file.
    """
    path_obj = Path(path)
    if path_obj.suffix.lower() != ".json":
        raise ValueError(
            f"load_transcript() only handles JSON files, got: {path_obj.suffix}. "
            "VTT files should be converted to JSON via transcript_importer.ensure_json_artifact() first."
        )
    resolved_path = path
    if not path_obj.exists():
        try:
            from transcriptx.core.utils._path_resolution import resolve_file_path

            resolved_path = resolve_file_path(path, file_type="transcript")
        except FileNotFoundError:
            raise FileNotFoundError(f"Transcript file not found: {path}") from None
    with open(resolved_path) as f:
        return json.load(f)


def load_transcript_data(
    transcript_path: str, skip_speaker_mapping: bool = False, batch_mode: bool = False
) -> TranscriptLoadResult:
    """
    Load and validate transcript data with standardized error handling.

    This function provides a common interface for loading transcript data
    across all analysis modules, ensuring consistent validation and error handling.

    DEPRECATED: Use TranscriptService.load_transcript_data() instead for caching support.
    This function is kept for backward compatibility and delegates to the service.

    Args:
        transcript_path: Path to the transcript JSON file
        skip_speaker_mapping: Skip speaker mapping if already done (default: False)
        batch_mode: Whether running in batch mode (default: False)

    Returns:
        TranscriptLoadResult (tuple-compatible: segments, base_name, transcript_dir, speaker_map)

    Raises:
        FileNotFoundError: If transcript file doesn't exist
        ValueError: If transcript file is invalid or empty
        Exception: For other loading errors
    """
    # Delegate to service for consistency and caching
    from transcriptx.io.transcript_service import get_transcript_service

    service = get_transcript_service()
    return service.load_transcript_data(
        transcript_path,
        skip_speaker_mapping=skip_speaker_mapping,
        batch_mode=batch_mode,
    )
