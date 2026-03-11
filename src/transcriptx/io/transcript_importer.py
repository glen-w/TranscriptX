"""
Centralised transcript importer interface.

Provides a single entry-point for importing transcripts from any supported
source format and creating standardised JSON artifacts.

Design invariants
-----------------
* **Single-read ingestion:** the source file is read into ``bytes`` exactly
  once via ``source_path.read_bytes()``.  ``compute_content_hash()`` operates
  on those bytes so no second disk read is needed.
* **Detection is registry-driven:** the ``AdapterRegistry`` selects the best
  adapter from registered candidates; the importer has no format-specific
  knowledge.
* **Already-normalised artifacts bypass re-import:** if a ``.json`` file is a
  valid TranscriptX schema v1.0 document (``schema_version`` + ``source`` +
  ``segments``), it is returned as-is.  If it fails validation it is treated
  as raw source data and re-imported through the adapter pipeline.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import DIARISED_TRANSCRIPTS_DIR
from transcriptx.io.adapters import registry
from transcriptx.io.segment_coalescer import CoalesceConfig, coalesce_segments
from transcriptx.io.speaker_normalizer import normalize_speakers
from transcriptx.io.transcript_normalizer import TranscriptNormalizer
from transcriptx.io.transcript_schema import (
    SourceInfo,
    TranscriptMetadata,
    compute_content_hash,
    create_transcript_document,
    validate_transcript_document,
)

logger = get_logger()


# ── Internal helpers ───────────────────────────────────────────────────────────


def _is_transcriptx_artifact(content: bytes) -> bool:
    """Return True if *content* looks like a TranscriptX schema v1.0 artifact.

    Checks for the presence of ``schema_version`` and ``source`` and
    ``segments`` at the top level.  Does not perform full validation.
    """
    try:
        data = json.loads(content.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return (
        isinstance(data, dict)
        and "schema_version" in data
        and "source" in data
        and "segments" in data
    )


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string with timezone offset."""
    return datetime.now(timezone.utc).isoformat()


# ── Public API ─────────────────────────────────────────────────────────────────


def detect_transcript_format(path: Path) -> str:
    """Return the ``source_id`` of the best-matching adapter for *path*.

    .. deprecated::
        This function's return-value semantics have changed: it now returns the
        adapter ``source_id`` (e.g. ``"sembly"``, ``"whisperx"``) rather than the
        old extension-derived strings (``"vtt"``, ``"srt"``, ``"json"``).
        Callers that branch on ``"json"`` must migrate to checking
        ``adapter.source_id`` or using ``isinstance(adapter, ...)`` directly.

    Raises:
        UnsupportedFormatError: If no adapter can handle the file.
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")
    content = path.read_bytes()
    adapter = registry.detect(path, content)
    return adapter.source_id


def ensure_json_artifact(path: Path, force_adapter: Optional[str] = None) -> Path:
    """Ensure a JSON artifact exists for the given transcript path.

    If *path* is already a valid TranscriptX schema v1.0 artifact, it is
    returned as-is without re-processing.  Otherwise ``import_transcript``
    is called to produce one.

    Args:
        path: Path to transcript file (any supported format or existing artifact).
        force_adapter: If given, bypass detection and use this adapter source_id.

    Returns:
        Path to the JSON artifact.
    """
    path = Path(path)
    if path.suffix.lower() == ".json":
        try:
            content = path.read_bytes()
            if _is_transcriptx_artifact(content):
                # Validate before accepting as-is
                data = json.loads(content.decode("utf-8", errors="replace"))
                try:
                    validate_transcript_document(data)
                    return path
                except ValueError as exc:
                    logger.warning(
                        f"Existing artifact failed validation ({exc}); "
                        "falling back to re-import."
                    )
        except OSError:
            pass  # fall through to import_transcript

    return import_transcript(path, force_adapter=force_adapter)


def import_transcript(
    source_path: str | Path,
    output_dir: Optional[str | Path] = None,
    coalesce_config: Optional[CoalesceConfig] = None,
    overwrite: bool = False,
    force_adapter: Optional[str] = None,
) -> Path:
    """Import a transcript file and create a standardised JSON artifact.

    Flow
    ----
    1.  Read source bytes **once**.
    2.  If file is an already-valid TranscriptX artifact, write it to the
        output location and return.  If it fails validation, fall through to
        re-import.
    3.  Detect the correct adapter via ``AdapterRegistry``.
    4.  Parse with the selected adapter → ``IntermediateTranscript``.
    5.  Repair with ``TranscriptNormalizer`` (logs only newly added warnings).
    6.  Normalise speakers with ``SpeakerNormalizer``.
    7.  (Optional) coalesce segments.
    8.  Build and write the schema v1.0 JSON artifact (hash from bytes, no
        second disk read).

    Args:
        source_path: Path to the source file (any supported format).
        output_dir: Directory for the JSON artifact.
            Defaults to ``DIARISED_TRANSCRIPTS_DIR``.
        coalesce_config: Optional segment coalescing configuration.
        overwrite: Whether to overwrite an existing JSON artifact.
        force_adapter: Bypass detection; use this adapter source_id directly.
            Raises ``UnsupportedFormatError`` immediately if unknown.

    Returns:
        Path to the created JSON artifact.

    Raises:
        FileNotFoundError: If source file doesn't exist.
        UnsupportedFormatError: If no adapter can handle the file.
        ValueError: If the resulting document is invalid.
    """
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    if output_dir is None:
        output_dir = Path(DIARISED_TRANSCRIPTS_DIR)
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_filename = source_path.stem + ".json"
    json_path = output_dir / json_filename

    if json_path.exists() and not overwrite:
        logger.info(f"JSON artifact already exists: {json_path}")
        return json_path

    # ── 1. Single file read ───────────────────────────────────────────────────
    content = source_path.read_bytes()

    # ── 2. Short-circuit: already a valid TranscriptX artifact ───────────────
    if source_path.suffix.lower() == ".json" and _is_transcriptx_artifact(content):
        try:
            data = json.loads(content.decode("utf-8", errors="replace"))
            validate_transcript_document(data)
            from transcriptx.core.store import TranscriptStore

            TranscriptStore().write(json_path, data, reason="import")
            logger.info(f"Passed through existing artifact: {json_path}")
            return json_path
        except ValueError as exc:
            logger.warning(
                f"Existing artifact failed validation ({exc}); re-importing via adapter."
            )
            # fall through to adapter detection

    # ── 3. Detect adapter ─────────────────────────────────────────────────────
    adapter = registry.detect(source_path, content, force_adapter=force_adapter)
    logger.info(
        f"Importing via {type(adapter).__name__} ({adapter.source_id!r}): {source_path.name}"
    )

    # ── 4. Parse ──────────────────────────────────────────────────────────────
    intermediate = adapter.parse(source_path, content)
    _log_warnings(intermediate.warnings, prefix=f"[{adapter.source_id}]")

    # ── 5. Normalise (repair timestamps, clean labels) ────────────────────────
    parse_warning_count = len(intermediate.warnings)
    normalizer = TranscriptNormalizer()
    turns = normalizer.normalize(intermediate)

    # Only log warnings added by the normalizer (not already logged above)
    new_norm_warnings = intermediate.warnings[parse_warning_count:]
    _log_warnings(new_norm_warnings, prefix="[normalizer]", level="debug")

    # ── 6. Speaker normalisation ──────────────────────────────────────────────
    segments = normalize_speakers(turns)

    # ── 7. Optional coalescing ────────────────────────────────────────────────
    if coalesce_config and coalesce_config.enabled:
        segments = coalesce_segments(segments, coalesce_config)

    # ── 8. Build metadata and artifact ───────────────────────────────────────
    duration = max((seg.get("end", 0) for seg in segments), default=0.0)
    speaker_ids = {seg.get("speaker") for seg in segments if seg.get("speaker")}
    metadata = TranscriptMetadata(
        duration_seconds=float(duration),
        segment_count=len(segments),
        speaker_count=len(speaker_ids),
    )

    # Hash from already-read bytes — no second disk read
    file_hash = compute_content_hash(content)
    file_mtime = os.path.getmtime(source_path)

    source_info = SourceInfo(
        type=adapter.source_id,
        original_path=str(source_path.resolve()),
        imported_at=_utc_now_iso(),
        file_hash=file_hash,
        file_mtime=file_mtime,
    )

    document = create_transcript_document(segments, source_info, metadata)
    validate_transcript_document(document)

    from transcriptx.core.store import TranscriptStore

    TranscriptStore().write(json_path, document, reason="import")

    logger.info(f"Created JSON artifact: {json_path}")
    logger.info(
        f"  adapter={adapter.source_id!r}  segments={metadata.segment_count}"
        f"  duration={metadata.duration_seconds:.2f}s  speakers={metadata.speaker_count}"
    )

    return json_path


# ── Logging helper ─────────────────────────────────────────────────────────────


def _log_warnings(
    warnings: list[str], *, prefix: str = "", level: str = "warning"
) -> None:
    log = logger.warning if level == "warning" else logger.debug
    for w in warnings:
        log(f"{prefix} {w}".strip())
