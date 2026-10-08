"""CLI: warm assistive LLM suggestion caches across the managed library.

Invoked as:

- ``transcriptx warm-suggestions …`` (console script)
- ``python -m transcriptx.warm_suggestions …``
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from transcriptx.app.models.requests import WarmSuggestionsRequest
from transcriptx.app.workflows.warm_suggestions import run_warm_suggestions


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcriptx warm-suggestions",
        description=(
            "Warm assistive rename and speaker-name suggestion caches for "
            "managed transcripts (confirm-to-apply in the GUI; never renames files)."
        ),
    )
    parser.add_argument(
        "--speaker-names",
        action="store_true",
        help="Warm speaker_name_suggestions caches for managed transcripts.",
    )
    parser.add_argument(
        "--rename",
        action="store_true",
        help="Warm rename_suggestions caches (requires rename_content_suggestions=auto).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Warm both speaker names and rename suggestions.",
    )
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        default=None,
        metavar="FILE",
        help="Managed transcript JSON (repeatable). Default: entire library.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute even when a valid cache entry exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List actionable targets without calling LLM or writing caches.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not (args.all or args.speaker_names or args.rename):
        print(
            "ERROR: pass --speaker-names, --rename, and/or --all",
            file=sys.stderr,
        )
        return 2

    from transcriptx._bootstrap import bootstrap
    from transcriptx.core.config.persistence import apply_project_config_to_live_facade

    bootstrap()
    apply_project_config_to_live_facade()

    paths = [Path(p).expanduser() for p in args.paths] if args.paths else None
    request = WarmSuggestionsRequest(
        warm_speaker_names=bool(args.speaker_names),
        warm_rename=bool(args.rename),
        warm_all=bool(args.all),
        transcript_paths=paths,
        force_refresh=bool(args.force),
        dry_run=bool(args.dry_run),
    )

    def _progress(index: int, total: int, label: str) -> None:
        print(f"  [{index}/{total}] {label}", file=sys.stderr)

    result = run_warm_suggestions(request, progress=_progress)
    for line in result.log_lines:
        if any(line.startswith(prefix) for prefix in ("ERROR",)):
            print(line, file=sys.stderr)
        else:
            print(f"  {line}")
    for err in result.errors:
        print(f"ERROR: {err}", file=sys.stderr)
    return 1 if result.error_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
