"""Import-metadata sidecar persistence: load, atomic write, and lifecycle mutations."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from transcriptx.core.observability.perf import record_file_read
from transcriptx.io.atomic_json import write_json_atomic as _write_json_atomic
from transcriptx.io.import_metadata.paths import sidecar_path_for_transcript
from transcriptx.io.import_metadata.schema import build_initial_sidecar


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    """Crash-safe staged JSON write (fsync file + best-effort parent dir)."""
    _write_json_atomic(path, payload, indent=2)


def load_sidecar(path: Path) -> dict[str, Any]:
    record_file_read(path, section="load_sidecar", purpose="metadata_extraction")
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Sidecar root must be an object")
    return data


def compute_rename_history_payload(
    sidecar_path: str | Path,
    *,
    old_filename: str,
    new_filename: str,
    at_iso: str,
) -> dict[str, Any]:
    """Validate sidecar and return the mutated payload (no write)."""
    sidecar = Path(sidecar_path)
    payload = load_sidecar(sidecar)
    history = payload.get("rename_history")
    if not isinstance(history, list):
        raise ValueError("rename_history must be a list")
    history = list(history)
    history.append(
        {
            "at": at_iso,
            "from_filename": old_filename,
            "to_filename": new_filename,
        }
    )
    payload = dict(payload)
    payload["rename_history"] = history
    payload["current_json_filename"] = new_filename
    return payload


def write_initial_sidecar(
    transcript_path: str | Path,
    *,
    import_id: str | None = None,
    imported_at: str,
    adapter_source_id: str,
    source_upload_basename: str,
    archived_original_relpath: str,
) -> Path:
    transcript = Path(transcript_path)
    sidecar = sidecar_path_for_transcript(transcript)
    payload = build_initial_sidecar(
        import_id=import_id or str(uuid.uuid4()),
        imported_at=imported_at,
        adapter_source_id=adapter_source_id,
        source_upload_basename=source_upload_basename,
        archived_original_relpath=archived_original_relpath,
        current_json_filename=transcript.name,
    )
    write_json_atomic(sidecar, payload)
    return sidecar


def append_rename_history(
    *,
    sidecar_path: str | Path,
    old_filename: str,
    new_filename: str,
    at_iso: str,
) -> None:
    payload = compute_rename_history_payload(
        sidecar_path,
        old_filename=old_filename,
        new_filename=new_filename,
        at_iso=at_iso,
    )
    write_json_atomic(Path(sidecar_path), payload)
