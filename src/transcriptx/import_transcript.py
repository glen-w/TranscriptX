"""CLI: managed-import one or more transcript files into the library.

Invoked as:

- ``transcriptx import …``
- ``python -m transcriptx.import_transcript …``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcriptx import",
        description=(
            "Import transcript file(s) into the managed library via "
            "run_managed_import_workflow (same path as Import Transcript in the GUI)."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        metavar="FILE",
        help="Raw transcript file(s) to admit (JSON/SRT/VTT/…).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing managed transcript with the same stem.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    from transcriptx._bootstrap import bootstrap

    bootstrap()

    from transcriptx.io.managed_import_workflow import run_managed_import_workflow

    exit_code = 0
    for raw in args.paths:
        path = raw.expanduser()
        try:
            result = run_managed_import_workflow(
                path,
                overwrite=bool(args.overwrite),
            )
        except Exception as exc:
            print(f"ERROR: {path}: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        print(f"ok: {path} -> {result.json_path}")
        if result.speaker_map_error:
            print(f"note: speaker map: {result.speaker_map_error}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
