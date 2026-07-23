#!/usr/bin/env python3
"""Backfill longitudinal speaker profiles from existing speaker-map names.

Offline one-off / maintenance tool. Managed library transcripts only.
Does not rewrite speaker-map sidecars.

Dry-run (default):
    uv run python scripts/backfill_speaker_profiles_from_maps.py

Apply:
    uv run python scripts/backfill_speaker_profiles_from_maps.py --apply

Options:
    --no-merge-by-name   Create a new profile per occurrence (no cross-transcript
                         attach by matching display name).
    --skip-name NAME     Extra display name to exclude (repeatable). Merged with
                         the default generic denylist (audience, academia, …).
    --verbose            Also list skip_not_named / skip_excluded_name rows.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python scripts/...` without installing editable when needed.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from transcriptx.services.speaker_profiles.backfill_from_maps import (  # noqa: E402
    DEFAULT_EXCLUDED_DISPLAY_NAMES,
    BackfillPlanItem,
    run_backfill_from_maps,
)

_DEFAULT_SHOWN = frozenset(
    {
        "create",
        "link",
        "skip_already_linked",
        "skip_ambiguous_name",
        "skip_ignored",
        "skip_resolver",
        "error",
    }
)


def _format_row(item: BackfillPlanItem) -> str:
    path = item.transcript_path.name
    mid = (item.managed_transcript_id or "-")[:8]
    target = item.target_profile_id or "-"
    if target.startswith("pending:"):
        target = "(new)"
    elif len(target) > 12:
        target = target[:8] + "…"
    detail = f"  {item.detail}" if item.detail else ""
    return (
        f"{item.action:22}  {path:40}  {item.local_speaker_key:12}  "
        f"{item.display_name!r:24}  profile={target}  import={mid}{detail}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill speaker profiles from speaker-map display names "
            "(managed library transcripts only)."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write profile/link mutations (default is dry-run).",
    )
    parser.add_argument(
        "--no-merge-by-name",
        action="store_true",
        help="Do not attach same display names across transcripts to one profile.",
    )
    parser.add_argument(
        "--skip-name",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Extra display name to exclude from profile creation (case-insensitive). "
            "Repeatable. Always merged with the default generic denylist."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Include skip_not_named and skip_excluded_name rows in the listing.",
    )
    args = parser.parse_args(argv)

    exclude = set(DEFAULT_EXCLUDED_DISPLAY_NAMES) | {
        n.strip() for n in (args.skip_name or []) if str(n).strip()
    }

    result = run_backfill_from_maps(
        apply=bool(args.apply),
        merge_by_name=not bool(args.no_merge_by_name),
        exclude_names=exclude,
    )

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] speaker-map → speaker profiles backfill")
    print(f"merge_by_name={not args.no_merge_by_name}")
    print(f"exclude_names={sorted(exclude)}")
    print()

    shown = set(_DEFAULT_SHOWN)
    if args.verbose:
        shown.add("skip_not_named")
        shown.add("skip_excluded_name")

    for item in result.items:
        if item.action in shown:
            print(_format_row(item))

    print()
    print("Counts:")
    for action, count in sorted(result.counts.items()):
        print(f"  {action}: {count}")

    if args.apply:
        print()
        print(f"Applied: {len(result.applied)}")
        print(f"Errors:  {len(result.errors)}")
        for err in result.errors:
            print(f"  ! {_format_row(err)}")

    if result.errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
