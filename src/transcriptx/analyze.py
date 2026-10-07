"""CLI: run analysis on one managed transcript.

Invoked as:

- ``transcriptx analyze …``
- ``python -m transcriptx.analyze …``

Interactive result browsing stays in the GUI. This command only runs the pipeline.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcriptx analyze",
        description=(
            "Run analysis on one managed library transcript "
            "(same engine as Run Analysis in the GUI)."
        ),
    )
    parser.add_argument(
        "--path",
        required=True,
        type=Path,
        metavar="FILE",
        help="Managed transcript JSON path.",
    )
    parser.add_argument(
        "--mode",
        choices=("quick", "full"),
        default="quick",
        help="Pipeline mode (default: quick).",
    )
    parser.add_argument(
        "--preset",
        dest="analysis_preset",
        choices=("quick", "balanced", "thorough", "custom"),
        default=None,
        help="Optional UI analysis preset persisted on the run.",
    )
    parser.add_argument(
        "--modules",
        default=None,
        metavar="IDS",
        help="Comma-separated module ids (default: recommended for mode/preset).",
    )
    parser.add_argument(
        "--allow-unnamed-speakers",
        action="store_true",
        help="Allow analysis when speakers are still diarized labels.",
    )
    parser.add_argument(
        "--include-unidentified-speakers",
        action="store_true",
        help="Include unidentified speakers in speaker-scoped modules.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    from transcriptx._bootstrap import bootstrap

    bootstrap()

    from transcriptx.app.models.requests import AnalysisRequest
    from transcriptx.app.workflows.analysis import run_analysis

    modules: list[str] | None = None
    if args.modules:
        modules = [m.strip() for m in str(args.modules).split(",") if m.strip()]
        if not modules:
            print("ERROR: --modules was empty after parsing", file=sys.stderr)
            return 2

    path = args.path.expanduser()
    if not path.is_file():
        print(f"ERROR: transcript not found: {path}", file=sys.stderr)
        return 2

    result = run_analysis(
        AnalysisRequest(
            transcript_path=path,
            mode=str(args.mode),
            analysis_preset=args.analysis_preset,
            modules=modules,
            allow_unnamed_speakers=bool(args.allow_unnamed_speakers),
            include_unidentified_speakers=bool(args.include_unidentified_speakers),
        )
    )
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    for err in result.errors:
        print(f"ERROR: {err}", file=sys.stderr)
    if result.success:
        print(f"ok: success status={result.status} run_dir={result.run_dir}")
        if result.modules_executed:
            print(f"modules: {', '.join(result.modules_executed)}")
        return 0
    print(
        f"failed: status={result.status} run_dir={result.run_dir}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
