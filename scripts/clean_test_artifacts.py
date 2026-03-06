#!/usr/bin/env python3
"""
Remove old testing artifacts from the outputs directory and slug index.

This prevents stagnant session dropdowns and "Transcript not found for session"
warnings in the web UI. By default targets slugs matching "test__" (e.g.
test__6, test__7). Use --prefix to change the pattern.

- Removes matching slug directories under data/outputs (or TRANSCRIPTX_OUTPUT_DIR).
- Removes those slugs from .transcriptx_index.json so they no longer appear
  in session lists.

Run with --dry-run (default) to see what would be removed. Use --apply --yes
to perform the cleanup.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Sequence

# Allow running from project root or scripts/
if __name__ == "__main__" and __package__ is None:
    _root = Path(__file__).resolve().parent.parent
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from transcriptx.core.utils.paths import OUTPUTS_DIR
from transcriptx.core.utils.slug_manager import (
    list_slugs_matching,
    unregister_slug,
)


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove test artifact slugs and their output directories.",
    )
    parser.add_argument(
        "--prefix",
        default="test__",
        help="Slug prefix to match (default: test__). Slugs like test__6, test__7 will be removed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Only print what would be removed (default).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually remove directories and index entries.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation when using --apply.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    outputs_dir = Path(OUTPUTS_DIR)

    if not outputs_dir.exists():
        print(f"Outputs directory does not exist: {outputs_dir}")
        return 0

    slugs = list_slugs_matching(args.prefix)
    if not slugs:
        print(f"No slugs matching prefix '{args.prefix}' found in index.")
        return 0

    # Check which slug dirs exist on disk
    to_remove: list[tuple[str, Path]] = []
    for slug in slugs:
        slug_dir = outputs_dir / slug
        if slug_dir.exists() and slug_dir.is_dir():
            to_remove.append((slug, slug_dir))
        else:
            to_remove.append((slug, Path()))  # index-only cleanup

    print(f"Slugs matching '{args.prefix}': {len(slugs)}")
    for slug, path in to_remove:
        if path and path.exists():
            run_count = sum(1 for p in path.iterdir() if p.is_dir() and not p.name.startswith("."))
            print(f"  - {slug}  ({path})  [{run_count} run(s)]")
        else:
            print(f"  - {slug}  (index only, no directory)")

    if args.apply:
        if not args.yes:
            confirm = input("Remove these slugs and their directories? [y/N]: ")
            if confirm.strip().lower() != "y":
                print("Aborted.")
                return 1
        for slug, path in to_remove:
            if path and path.exists():
                try:
                    shutil.rmtree(path)
                    print(f"Removed directory: {path}")
                except Exception as e:
                    print(f"Failed to remove {path}: {e}", file=sys.stderr)
            if unregister_slug(slug):
                print(f"Removed from index: {slug}")
        print("Done.")
    else:
        print("\nDry run. Use --apply --yes to perform the cleanup.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
