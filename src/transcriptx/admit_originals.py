"""CLI: admit originals/ transcripts into the managed library.

Invoked as ``python -m transcriptx.admit_originals`` (not ``transcriptx <subcommand>``).

Sets ``TRANSCRIPTX_TRANSCRIPTS_DIR`` from ``--transcripts-root`` *after* ``.env``
bootstrap and *before* importing path constants, so inbox-watch can point admit
at the same library the host JSON was written to.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Sequence


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Admit raw transcripts from originals/ (or another host dest) "
            "into the managed library via admit_and_register."
        ),
    )
    parser.add_argument(
        "--dir",
        dest="directory",
        type=Path,
        required=True,
        help="Folder to scan (typically …/transcripts/originals).",
    )
    parser.add_argument(
        "--transcripts-root",
        dest="transcripts_root",
        type=Path,
        default=None,
        help=(
            "Managed library root (parent of originals/). "
            "Overrides TRANSCRIPTX_TRANSCRIPTS_DIR after .env load."
        ),
    )
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        metavar="NAME",
        help="Admit only these basenames in --dir (default: all eligible files).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List candidates; do not admit.",
    )
    name_group = parser.add_mutually_exclusive_group()
    name_group.add_argument(
        "--auto-name",
        dest="auto_name",
        action="store_true",
        default=None,
        help="After admit, auto-write speaker display names (implies identify).",
    )
    name_group.add_argument(
        "--no-auto-name",
        dest="auto_name",
        action="store_false",
        help="Do not auto-name speakers after admit.",
    )
    link_group = parser.add_mutually_exclusive_group()
    link_group.add_argument(
        "--auto-link",
        dest="auto_link",
        action="store_true",
        default=None,
        help="After admit, auto-link matched longitudinal profiles.",
    )
    link_group.add_argument(
        "--no-auto-link",
        dest="auto_link",
        action="store_false",
        help="Do not auto-link profiles after admit.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    from transcriptx._bootstrap import bootstrap

    bootstrap()
    if args.transcripts_root is not None:
        os.environ["TRANSCRIPTX_TRANSCRIPTS_DIR"] = str(
            args.transcripts_root.expanduser().resolve()
        )

    from transcriptx.io.admit_originals import run_admit_originals

    return run_admit_originals(
        args.directory.expanduser(),
        only=args.only,
        dry_run=bool(args.dry_run),
        auto_name=args.auto_name,
        auto_link=args.auto_link,
    )


if __name__ == "__main__":
    raise SystemExit(main())
