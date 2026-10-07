"""CLI: non-interactive bulk analysis-run cleanup.

Invoked as:

- ``transcriptx cleanup-runs …``
- ``python -m transcriptx.cleanup_runs …``

Uses the same ``RunCleanupService`` journal/staging path as Settings → Storage.
Does not require Streamlit.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from typing import Sequence

from transcriptx.web.services.run_cleanup import (
    CONFIRM_DELETE_ALL,
    CONFIRM_DELETE_OLD,
    CleanupAuthorization,
    CleanupMode,
    CleanupRetainPolicy,
    CleanupStatus,
    RunCleanupService,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="transcriptx cleanup-runs",
        description=(
            "Bulk-delete analysis run directories (same engine as Settings → Storage). "
            "With --keep-human-readable / --keep-llm-summaries under delete-old, "
            "matching files are copied to {subject}/.retained/{run_id}/ before delete."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("delete-old", "delete-all"),
        required=True,
        help="delete-old keeps the newest run per subject; delete-all removes every run.",
    )
    parser.add_argument(
        "--keep-human-readable",
        action="store_true",
        help=(
            "Before deleting an old run, copy transcripts/*.{txt,csv,srt,vtt} "
            "and report.md/report.txt into .retained/{run_id}/."
        ),
    )
    parser.add_argument(
        "--keep-llm-summaries",
        action="store_true",
        help=(
            "Before deleting an old run, copy *_llm_summary.md / *_llm_summary.json "
            "into .retained/{run_id}/."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview only: print plan counts and exit without deleting.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help=(
            "Required for a live delete (or set TRANSCRIPTX_CLEANUP_YES=1). "
            "Supplies the confirm phrase non-interactively."
        ),
    )
    parser.add_argument(
        "--session-id",
        default=None,
        metavar="ID",
        help="Optional cleanup handle session id (default: random).",
    )
    return parser.parse_args(argv)


def _mode_from_cli(raw: str) -> CleanupMode:
    if raw == "delete-old":
        return CleanupMode.DELETE_OLD
    if raw == "delete-all":
        return CleanupMode.DELETE_ALL
    raise ValueError(f"unsupported mode: {raw!r}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    from transcriptx._bootstrap import bootstrap

    bootstrap()

    mode = _mode_from_cli(args.mode)
    retain = CleanupRetainPolicy(
        keep_human_readable=bool(args.keep_human_readable),
        keep_llm_summaries=bool(args.keep_llm_summaries),
    )
    if retain.enabled and mode is not CleanupMode.DELETE_OLD:
        print(
            "ERROR: --keep-* flags are only valid with --mode delete-old",
            file=sys.stderr,
        )
        return 2

    session_id = args.session_id or f"cli-{uuid.uuid4().hex}"
    svc = RunCleanupService()
    handle, preview = svc.preview_cleanup(
        mode, session_id, retain_policy=retain
    )

    print(f"mode: {mode.value}")
    print(f"plan_id: {preview.plan_id}")
    print(
        f"candidates: {preview.run_count} runs · "
        f"~{preview.file_count} files · ~{preview.size_estimate_bytes} bytes"
    )
    print(
        f"subjects: transcript={preview.transcript_subjects} "
        f"group={preview.group_subjects}"
    )
    print(f"retained (newest kept): {len(preview.retained)}")
    if retain.enabled:
        print(
            "retain: "
            f"human_readable={retain.keep_human_readable} "
            f"llm_summaries={retain.keep_llm_summaries}"
        )
    for warn in preview.warnings:
        print(f"warning: {warn}", file=sys.stderr)
    for err in preview.blocking_errors:
        print(f"ERROR: {err}", file=sys.stderr)

    if args.dry_run:
        print("dry-run: no delete performed")
        return 1 if preview.blocking_errors else 0

    if not preview.can_execute or preview.blocking_errors:
        print("ERROR: plan cannot execute", file=sys.stderr)
        return 1

    yes_env = os.environ.get("TRANSCRIPTX_CLEANUP_YES", "").strip() in {
        "1",
        "true",
        "yes",
        "YES",
    }
    if not (args.yes or yes_env):
        phrase = (
            CONFIRM_DELETE_OLD
            if mode is CleanupMode.DELETE_OLD
            else CONFIRM_DELETE_ALL
        )
        print(
            f"ERROR: refusing live delete without --yes "
            f"(or TRANSCRIPTX_CLEANUP_YES=1). Confirm phrase would be: {phrase!r}",
            file=sys.stderr,
        )
        return 2

    if preview.run_count == 0:
        print("ok: nothing to delete (NOOP)")
        return 0

    phrase = (
        CONFIRM_DELETE_OLD if mode is CleanupMode.DELETE_OLD else CONFIRM_DELETE_ALL
    )
    auth = CleanupAuthorization(
        acknowledged=True,
        phrase=phrase,
        mode=mode,
        plan_id=preview.plan_id,
    )
    result = svc.execute_cleanup(handle, auth, session_id)
    print(
        f"status: {result.status.value} · "
        f"visible_removed={result.visible_removed_count} · "
        f"physically_deleted={result.physically_deleted_count} · "
        f"operation_id={result.operation_id or '(none)'}"
    )
    for warn in result.warnings:
        print(f"warning: {warn}", file=sys.stderr)
    for err in result.errors:
        print(f"ERROR: {err}", file=sys.stderr)

    if result.status in {
        CleanupStatus.SUCCESS,
        CleanupStatus.NOOP,
        CleanupStatus.ALREADY_EXECUTED,
    }:
        return 0
    if result.status is CleanupStatus.PARTIAL:
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
