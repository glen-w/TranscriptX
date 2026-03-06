"""
DB-free CLI commands for transcript validation and canonicalization.

This module must not import database or anything that triggers SQLite init.
Commands: transcript validate, transcript canonicalize.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console

# Only import IO/schema; no database, no core.services
from transcriptx.core.store import TranscriptStore
from transcriptx.io.transcript_loader import normalize_segments
from transcriptx.io.transcript_schema import (
    SourceInfo,
    create_transcript_document,
    validate_transcript_document,
)

console = Console()
err_console = Console(stderr=True)

SPEAKER_UNKNOWN = "SPEAKER_UNKNOWN"


def _normalize_speaker(s: Any) -> str:
    """Normalize speaker to string; missing/null/empty -> SPEAKER_UNKNOWN."""
    if s is None:
        return SPEAKER_UNKNOWN
    if isinstance(s, str) and s.strip():
        return s.strip()
    return SPEAKER_UNKNOWN


def validate_cmd(
    file: Path = typer.Option(..., "--file", "-f", help="Path to transcript JSON"),
) -> None:
    """Validate a transcript JSON file against the canonical schema."""
    if not file.exists():
        err_console.print(f"[red]File not found: {file}[/red]")
        raise SystemExit(2)
    try:
        with open(file) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        err_console.print(f"[red]Invalid JSON: {e}[/red]")
        raise SystemExit(2)

    if not isinstance(data, dict):
        err_console.print("[red]Root must be a JSON object.[/red]")
        raise SystemExit(1)

    if "schema_version" in data:
        try:
            validate_transcript_document(data)
            meta = data.get("metadata") or {}
            segs = data.get("segments") or []
            console.print("[green]Valid[/green] canonical transcript.")
            console.print(f"  schema_version: {data.get('schema_version')}")
            console.print(f"  segment_count: {len(segs)}")
            console.print(f"  speaker_count: {meta.get('speaker_count', 'N/A')}")
            console.print(f"  duration_seconds: {meta.get('duration_seconds', 'N/A')}")
            return
        except ValueError as e:
            err_console.print(f"[red]Validation failed: {e}[/red]")
            raise SystemExit(1)

    # No schema_version: check if loadable (e.g. raw WhisperX)
    try:
        segments = normalize_segments(data)
        if segments:
            err_console.print(
                "[yellow]Loadable but not canonical[/yellow] (no schema_version). "
                "Recommend: transcriptx transcript canonicalize --in <file> --out <file>"
            )
            raise SystemExit(1)
    except Exception:
        pass
    err_console.print(
        "[red]Invalid: missing schema_version and not a loadable segment format.[/red]"
    )
    raise SystemExit(1)


def canonicalize_cmd(
    in_path: Path = typer.Option(..., "--in", "-i", help="Input transcript JSON"),
    out_path: Optional[Path] = typer.Option(
        None, "--out", "-o", help="Output path (default: <stem>_transcriptx.json)"
    ),
    source_type: str = typer.Option(
        "whisperx",
        "--source-type",
        "-s",
        help="Source type (e.g. whisperx, vtt, manual)",
    ),
) -> None:
    """Convert transcript JSON to canonical TranscriptX format."""
    if not in_path.exists():
        err_console.print(f"[red]File not found: {in_path}[/red]")
        raise SystemExit(2)
    try:
        with open(in_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        err_console.print(f"[red]Invalid JSON: {e}[/red]")
        raise SystemExit(2)

    segments = normalize_segments(data)
    for seg in segments:
        if isinstance(seg, dict):
            seg["speaker"] = _normalize_speaker(seg.get("speaker"))

    if not out_path:
        out_path = in_path.parent / f"{in_path.stem}_transcriptx.json"

    source_info = SourceInfo(
        type=source_type,
        original_path=str(in_path),
        imported_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        file_hash=None,
        file_mtime=None,
    )
    doc = create_transcript_document(segments, source_info, metadata=None)
    try:
        TranscriptStore().write(out_path, doc, reason="canonicalize")
    except OSError as e:
        err_console.print(f"[red]Write failed: {e}[/red]")
        raise SystemExit(2)
    console.print(f"[green]Wrote[/green] {out_path}")
    console.print(
        f"  segments={doc['metadata']['segment_count']} "
        f"speakers={doc['metadata']['speaker_count']} "
        f"duration={doc['metadata']['duration_seconds']:.1f}s"
    )


def register_transcript_file_commands(transcript_app: typer.Typer) -> None:
    """Register validate and canonicalize on the transcript Typer app."""
    transcript_app.command(
        "validate", help="Validate transcript JSON against canonical schema"
    )(validate_cmd)
    transcript_app.command(
        "canonicalize", help="Convert transcript JSON to canonical TranscriptX format"
    )(canonicalize_cmd)
