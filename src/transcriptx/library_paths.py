"""CLI: list managed transcript paths for night automation.

Invoked as ``transcriptx library-paths …``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcriptx library-paths",
        description="Print managed transcript paths (newest first).",
    )
    parser.add_argument(
        "--recent",
        type=int,
        default=0,
        metavar="N",
        help="Keep only the N newest paths by mtime (0 = all).",
    )
    parser.add_argument(
        "--missing-modules",
        default="",
        metavar="IDS",
        help=(
            "Comma-separated module ids; keep only paths missing at least one "
            "(same rules as analyze-modules). Implies sorting by mtime."
        ),
    )
    return parser.parse_args(argv)


def _newest_first(paths: list[Path], limit: int) -> list[Path]:
    ordered = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
    if limit > 0:
        return ordered[:limit]
    return ordered


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    from transcriptx._bootstrap import bootstrap

    bootstrap()

    from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths

    raw = [Path(p) for p in discover_managed_transcript_paths()]
    if args.missing_modules:
        from transcriptx.analyze_modules import _discover_targets, _parse_modules

        mods = list(_parse_modules(args.missing_modules))
        want = {str(t[0]) for t in _discover_targets(modules=mods, force=False)}
        raw = [p for p in raw if str(p) in want]

    limit = int(args.recent or 0)
    for path in _newest_first(raw, limit):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
