"""
Transcript loading utilities for TranscriptX.

Runtime loading accepts **only** schema v1.0 JSON artifacts produced by the
import pipeline (``schema_version`` + ``source`` + ``segments``). Any other
shape must go through ``transcript_importer.ensure_json_artifact`` /
``import_transcript()`` or ``load_segments`` / ``load_transcript`` will raise
``ValueError``.

Path resolution invariant (canonical)
--------------------------------------
All file-path resolution for transcripts is owned by this layer (and
_path_resolution). If the input path exists, it is used. If missing,
resolution is attempted via _path_resolution.resolve_file_path(path, file_type="transcript")
(e.g. renamed files after speaker mapping).

Public surface: ``load_segments()``, ``load_transcript()``, ``TranscriptLoadResult``.
``load_transcript_data`` lives on ``TranscriptService`` (and is re-exported from
``transcriptx.io`` for convenience).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

from transcriptx.io.transcript_schema import validate_transcript_document


class TranscriptLoadResult(NamedTuple):
    """
    Result of loading transcript data (segments, paths).

    Returned by TranscriptService.load_transcript_data.
    Tuple-unpacking remains valid: segments, base_name, transcript_dir = result
    """

    segments: List[Dict[str, Any]]
    base_name: str
    transcript_dir: str


def _require_canonical_v1_document(data: Any, *, label: str) -> List[Dict[str, Any]]:
    """Return segments from a schema v1.0 artifact dict or raise ValueError."""
    if not isinstance(data, dict):
        raise ValueError(
            f"{label}: transcript data must be a JSON object (schema v1.0 artifact). "
            "Use transcript_importer.ensure_json_artifact() to convert raw sources."
        )
    if "schema_version" not in data or "source" not in data:
        raise ValueError(
            f"{label}: missing schema v1.0 artifact markers "
            "(required keys: schema_version, source). "
            "Use transcript_importer.ensure_json_artifact() or import_transcript()."
        )
    validate_transcript_document(data)
    segments = data.get("segments", [])
    if not isinstance(segments, list):
        raise ValueError(f"{label}: 'segments' must be a list")
    return segments


def load_segments(path: str, data: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Load segments from a canonical schema v1.0 transcript JSON file or dict.

    Args:
        path: Path to the transcript JSON file. Required even when *data* is
            provided (used for error messages).
        data: Optional pre-loaded artifact dict. When provided the file is not read.

    Returns:
        List of segment dicts (non-empty ``speaker`` strings per schema).

    Raises:
        FileNotFoundError: File not found and path resolution fails.
        ValueError: Path is not ``.json``, or data is not a valid v1.0 artifact.
    """
    if data is not None:
        return _require_canonical_v1_document(
            data, label=f"transcript data for {path!r}"
        )

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

    with open(resolved_path, encoding="utf-8") as f:
        file_data = json.load(f)

    return _require_canonical_v1_document(
        file_data, label=f"transcript file {resolved_path!r}"
    )


def load_canonical_transcript(path: str) -> "CanonicalTranscript":
    """
    Load a transcript file and return a CanonicalTranscript instance.
    """
    from transcriptx.core.domain.canonical_transcript import CanonicalTranscript

    segments = load_segments(path)
    if not segments:
        raise ValueError(f"No segments found in transcript: {path}")
    return CanonicalTranscript.from_segments(segments)


def load_transcript(path: str) -> Any:
    """
    Load a complete transcript file as JSON (raw structure, no segment validation).

    Use ``load_segments`` when you need validated segment lists.
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
    with open(resolved_path, encoding="utf-8", errors="replace") as f:
        content = f.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        start = max(0, e.pos - 80)
        end = min(len(content), e.pos + 80)
        snippet = content[start:end]
        snippet = snippet.replace("\n", " ").replace("\r", " ")
        if start > 0:
            snippet = "…" + snippet
        if end < len(content):
            snippet = snippet + "…"
        raise json.JSONDecodeError(
            f"{e.msg}. Near position {e.pos} (line {e.lineno} column {e.colno}): {snippet!r}",
            e.doc,
            e.pos,
        ) from e
