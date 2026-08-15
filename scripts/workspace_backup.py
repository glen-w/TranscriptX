#!/usr/bin/env python3
"""Create / verify / restore full-workspace backup ZIPs.

Helper script (not a ``transcriptx`` console subcommand). Prefer this for large
corpora; Settings → Storage exposes the same service with on-disk paths.

Examples:
    uv run python scripts/workspace_backup.py create
    uv run python scripts/workspace_backup.py create --dest /safe/ws.zip --force
    uv run python scripts/workspace_backup.py verify /safe/ws.zip
    uv run python scripts/workspace_backup.py restore /safe/ws.zip --dry-run
    uv run python scripts/workspace_backup.py restore /safe/ws.zip --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from transcriptx.app.models.errors import BackupError  # noqa: E402
from transcriptx.services.workspace_backup import (  # noqa: E402
    BackupOptions,
    WorkspaceBackupService,
    default_backup_dest,
    get_default_paths,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Full-workspace backup ZIP create / verify / restore. "
            "Helper only — not a transcriptx console subcommand."
        )
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Write a workspace backup ZIP")
    p_create.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Destination .zip (default: {DATA}/backups/workspace/transcriptx-workspace-<stamp>.zip)",
    )
    p_create.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing destination ZIP",
    )
    p_create.add_argument(
        "--include-recordings",
        action="store_true",
        help="Also pack TRANSCRIPTX_RECORDINGS_DIR",
    )
    p_create.add_argument(
        "--include-outputs",
        action="store_true",
        help="Also pack TRANSCRIPTX_OUTPUT_DIR",
    )

    p_verify = sub.add_parser("verify", help="Verify a workspace backup ZIP")
    p_verify.add_argument("archive", type=Path)

    p_restore = sub.add_parser(
        "restore",
        help="Replace the current workspace from a backup ZIP",
    )
    p_restore.add_argument("archive", type=Path)
    p_restore.add_argument(
        "--dry-run",
        action="store_true",
        help="Describe replacements without writing",
    )
    p_restore.add_argument(
        "--yes",
        action="store_true",
        help="Required for a live (non-dry-run) restore",
    )
    p_restore.add_argument(
        "--no-safety-backup",
        action="store_true",
        help="Skip automatic pre-restore safety ZIP",
    )

    args = parser.parse_args(argv)
    paths = get_default_paths()
    service = WorkspaceBackupService()

    try:
        if args.cmd == "create":
            dest = Path(args.dest) if args.dest else default_backup_dest(paths)
            result = service.create_backup(
                paths,
                dest,
                BackupOptions(
                    include_recordings=bool(args.include_recordings),
                    include_outputs=bool(args.include_outputs),
                ),
                force=bool(args.force),
            )
            counts = result.manifest.get("counts") or {}
            print(
                f"ok: wrote {result.archive_path} "
                f"(transcripts={counts.get('transcripts')} "
                f"files={counts.get('files')} "
                f"uncompressed_bytes={counts.get('uncompressed_bytes')})"
            )
            return 0

        if args.cmd == "verify":
            result = service.verify_backup(Path(args.archive))
            counts = result.manifest.get("counts") or {}
            print(
                "ok: backup verified "
                f"(transcripts={counts.get('transcripts')}, files={counts.get('files')})"
            )
            for message in result.messages:
                print(f"note: {message}")
            return 0

        if args.cmd == "restore":
            if not args.dry_run and not args.yes:
                print(
                    "error: live restore requires --yes (or pass --dry-run)",
                    file=sys.stderr,
                )
                return 2
            result = service.restore_backup(
                paths,
                Path(args.archive),
                safety=not bool(args.no_safety_backup),
                dry_run=bool(args.dry_run),
            )
            for message in result.messages:
                print(message)
            if result.safety_archive is not None:
                print(f"safety_archive: {result.safety_archive}")
            if not result.ok:
                print("error: restore finished with integrity issues", file=sys.stderr)
                return 1
            print("ok: restore complete" if not result.dry_run else "ok: dry-run complete")
            return 0
    except BackupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"error: unknown command {args.cmd!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
