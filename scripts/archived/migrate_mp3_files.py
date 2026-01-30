#!/usr/bin/env python3
"""
Migration script to move MP3 files from data/outputs/recordings/ to data/recordings/

This is a one-off migration to reorganize the file structure.
"""

import argparse
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OLD_RECORDINGS_DIR = PROJECT_ROOT / "data" / "outputs" / "recordings"
NEW_RECORDINGS_DIR = PROJECT_ROOT / "data" / "recordings"


def move_with_conflict_handling(src: Path, dst: Path, overwrite: bool, dry_run: bool) -> None:
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


def migrate_mp3_files(overwrite: bool = False, dry_run: bool = False) -> None:
    """
    Migrate all MP3 files from data/outputs/recordings/ to data/recordings/.
    
    Args:
        overwrite: If True, overwrite existing destination files
        dry_run: If True, only print what would be done without moving files
    """
    if not OLD_RECORDINGS_DIR.exists():
        print(f"Old recordings directory does not exist: {OLD_RECORDINGS_DIR}")
        return
    
    # Ensure target directory exists
    NEW_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    
    migrated_count = 0
    skipped_count = 0
    
    # Find all MP3 files in the old directory
    mp3_files = list(OLD_RECORDINGS_DIR.glob("*.mp3"))
    
    if not mp3_files:
        print(f"No MP3 files found in {OLD_RECORDINGS_DIR}")
        return
    
    for mp3_file in sorted(mp3_files):
        if not mp3_file.is_file():
            continue
        
        target_file = NEW_RECORDINGS_DIR / mp3_file.name
        
        if target_file.exists() and not overwrite:
            print(f"SKIP: {mp3_file} (target exists: {target_file})")
            skipped_count += 1
            continue
        
        move_with_conflict_handling(mp3_file, target_file, overwrite, dry_run)
        migrated_count += 1
    
    print(f"\nMigration complete:")
    print(f"  Migrated: {migrated_count}")
    print(f"  Skipped: {skipped_count}")
    
    # If all files were migrated and directory is empty, optionally remove it
    if not dry_run and migrated_count > 0:
        remaining_files = list(OLD_RECORDINGS_DIR.glob("*"))
        if not remaining_files:
            try:
                OLD_RECORDINGS_DIR.rmdir()
                print(f"Removed empty directory: {OLD_RECORDINGS_DIR}")
            except OSError as e:
                print(f"Could not remove directory {OLD_RECORDINGS_DIR}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate MP3 files from data/outputs/recordings/ to data/recordings/"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing destination files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without moving files"
    )
    args = parser.parse_args()
    
    migrate_mp3_files(overwrite=args.overwrite, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

