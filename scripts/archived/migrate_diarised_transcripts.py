#!/usr/bin/env python3
"""
Migration script to move diarised transcript JSONs from
data/outputs/{session}/transcripts/{session}_transcript_diarised.json
to data/transcripts/

This is a one-off migration to reorganize the file structure.
"""

import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = PROJECT_ROOT / "data" / "outputs"
TARGET_DIR = PROJECT_ROOT / "data" / "transcripts"


def move_with_conflict_handling(
    src: Path, dst: Path, overwrite: bool, dry_run: bool
) -> None:
    """
    Move file with conflict handling.

    Args:
        src: Source file path
        dst: Destination file path
        overwrite: If True, overwrite existing files
        dry_run: If True, only print what would be done
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    final_dst = dst

    if dst.exists() and not overwrite:
        stem = dst.stem
        suffix = dst.suffix
        i = 1
        while True:
            candidate = dst.with_name(f"{stem}__{i}{suffix}")
            if not candidate.exists():
                final_dst = candidate
                break
            i += 1

    if dry_run:
        print(f"DRY-RUN: {src} -> {final_dst}")
        return

    shutil.move(str(src), str(final_dst))
    print(f"Moved: {src} -> {final_dst}")


def migrate_diarised_transcripts(
    overwrite: bool = False, dry_run: bool = False
) -> None:
    """
    Migrate all diarised transcript JSONs from outputs subfolders to data/transcripts/.

    Args:
        overwrite: If True, overwrite existing destination files
        dry_run: If True, only print what would be done without moving files
    """
    if not OUTPUTS_DIR.exists():
        print(f"Outputs directory does not exist: {OUTPUTS_DIR}")
        return

    # Ensure target directory exists
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    migrated_count = 0
    skipped_count = 0

    # Scan all subdirectories in outputs
    for session_dir in sorted(OUTPUTS_DIR.iterdir()):
        if not session_dir.is_dir():
            continue

        session_name = session_dir.name

        # Look for transcripts subdirectory
        transcripts_dir = session_dir / "transcripts"
        if not transcripts_dir.exists() or not transcripts_dir.is_dir():
            continue

        # Look for diarised transcript file
        diarised_file = transcripts_dir / f"{session_name}_transcript_diarised.json"

        if diarised_file.exists() and diarised_file.is_file():
            target_file = TARGET_DIR / diarised_file.name

            if target_file.exists() and not overwrite:
                print(f"SKIP: {diarised_file} (target exists: {target_file})")
                skipped_count += 1
                continue

            move_with_conflict_handling(diarised_file, target_file, overwrite, dry_run)
            migrated_count += 1

    print("\nMigration complete:")
    print(f"  Migrated: {migrated_count}")
    print(f"  Skipped: {skipped_count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate diarised transcripts from outputs/{session}/transcripts/ to data/transcripts/"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing destination files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print actions without moving files"
    )
    args = parser.parse_args()

    migrate_diarised_transcripts(overwrite=args.overwrite, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
