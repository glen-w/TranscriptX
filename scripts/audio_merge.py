#!/usr/bin/env python3
"""Merge multiple audio files into one MP3 (helper script; not a GUI surface).

Not part of the core TranscriptX product path (import → analyze). Use when
split recorder parts should become one file before external transcription.
Candidate for removal in 1.2 — see docs/ROADMAP.md.

Examples:
    uv run python scripts/audio_merge.py part_1.wav part_2.wav -o merged.mp3
    uv run python scripts/audio_merge.py --list paths.txt --no-backup --overwrite
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from transcriptx.app.models.requests import MergeRequest  # noqa: E402
from transcriptx.app.workflows.merge import run_merge  # noqa: E402


def _paths_from_args(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = []
    if args.list_file is not None:
        text = args.list_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                paths.append(Path(line))
    paths.extend(Path(p) for p in args.inputs)
    return [p.resolve() for p in paths]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Merge two or more audio files into one MP3. "
            "Helper only — not a supported GUI or core product surface."
        )
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Input audio paths in merge order (at least two total with --list)",
    )
    parser.add_argument(
        "--list",
        type=Path,
        dest="list_file",
        default=None,
        help="Text file of paths (one per line; # comments allowed)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output MP3 path (default: recordings dir with date-prefixed name)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not copy originals into storage backup before merge",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output",
    )
    parser.add_argument(
        "--delete-originals",
        action="store_true",
        help="Delete source files and any linked part transcripts after a successful merge",
    )
    parser.add_argument(
        "--preprocess",
        action="store_true",
        help=(
            "Apply current preprocessing defaults to each file before concatenating "
            "(off by default; otherwise run scripts/audio_preprocess.py separately)"
        ),
    )
    args = parser.parse_args(argv)

    file_paths = _paths_from_args(args)
    if len(file_paths) < 2:
        print(
            "error: need at least two input files (positional and/or --list)",
            file=sys.stderr,
        )
        return 2

    output_dir = None
    output_filename = None
    if args.output is not None:
        out = args.output.resolve()
        output_dir = out.parent
        output_filename = out.name

    result = run_merge(
        MergeRequest(
            file_paths=file_paths,
            output_dir=output_dir,
            output_filename=output_filename,
            backup_wavs=not args.no_backup,
            overwrite=args.overwrite,
            delete_originals=args.delete_originals,
            apply_preprocessing=args.preprocess,
        )
    )
    if not result.success:
        for err in result.errors:
            print(f"error: {err}", file=sys.stderr)
        return 1

    print(f"merged: {result.files_merged} file(s)")
    if result.output_path:
        print(f"output: {result.output_path}")
    for w in result.warnings:
        print(f"warning: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
