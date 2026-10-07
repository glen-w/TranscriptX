"""CLI: rename a managed library transcript (and linked audio).

Invoked as:

- ``transcriptx rename …``
- ``python -m transcriptx.rename_managed …``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcriptx rename",
        description=(
            "Rename a managed transcript via rename_managed_transcript "
            "(same path as Rename Transcript in the GUI)."
        ),
    )
    parser.add_argument(
        "--path",
        required=True,
        type=Path,
        metavar="FILE",
        help="Current managed transcript JSON path.",
    )
    parser.add_argument(
        "--stem",
        required=True,
        help="New base name (stem) without .json extension.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan the rename without writing.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    from transcriptx._bootstrap import bootstrap

    bootstrap()

    from transcriptx.core.utils.rename.pipeline import rename_managed_transcript

    path = args.path.expanduser()
    if not path.is_file():
        print(f"ERROR: transcript not found: {path}", file=sys.stderr)
        return 2

    outcome = rename_managed_transcript(
        path,
        str(args.stem),
        dry_run=bool(args.dry_run),
    )
    if outcome.message:
        print(outcome.message)
    if outcome.new_transcript_path:
        print(f"new_path: {outcome.new_transcript_path}")
    print(f"status: {outcome.status.value}")
    for warning in outcome.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for err in outcome.errors:
        print(f"ERROR: {err.code}: {err.message}", file=sys.stderr)

    if outcome.ok or outcome.partial_success_after_transaction:
        return 0 if outcome.ok else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
