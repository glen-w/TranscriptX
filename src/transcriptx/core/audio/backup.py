"""
Pure audio backup helpers — no UI or presentation logic.

App and web layers import from here.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import PATHS, RECORDINGS_IMPORTS_DIR

logger = get_logger()


def _is_under_imports(path: Path) -> bool:
    """True if path is under RECORDINGS_IMPORTS_DIR (app-controlled uploads)."""
    try:
        path.resolve().relative_to(RECORDINGS_IMPORTS_DIR.resolve())
        return True
    except ValueError:
        return False


def backup_audio_files_to_storage(
    audio_paths: list[Path],
    base_name: Optional[str] = None,
    delete_original: bool = True,
) -> list[Path]:
    """
    Back up multiple audio files to the WAV storage directory.

    Files are renamed to {base_name}_{idx+1}{suffix} when base_name is given,
    or keep their original stem otherwise.  The destination directory is
    created if it does not exist.

    Args:
        audio_paths: Files to back up, in order.
        base_name: Optional shared stem for numbered backups
                   (e.g. "260108_merged" → "260108_merged_1.wav").
        delete_original: Delete source file after a successful copy (default True).
            As a safeguard, we only delete when the source is under RECORDINGS_IMPORTS_DIR
            (uploads). Files in the recordings root or elsewhere are never deleted.

    Returns:
        Paths of the created backup files (failures are silently skipped).
    """
    if not audio_paths:
        return []

    storage_dir = Path(PATHS.wav_backup_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)

    backup_paths: List[Path] = []
    for idx, src_path in enumerate(audio_paths):
        try:
            if not src_path.exists():
                logger.warning(f"Audio file not found, skipping backup: {src_path}")
                continue

            suffix = src_path.suffix.lower()
            backup_stem = f"{base_name}_{idx + 1}" if base_name else src_path.stem

            dest_path = storage_dir / f"{backup_stem}{suffix}"
            counter = 1
            while dest_path.exists():
                dest_path = storage_dir / f"{backup_stem}_{counter}{suffix}"
                counter += 1
                if counter > 1000:
                    logger.warning(
                        f"Too many name conflicts for {backup_stem}, skipping"
                    )
                    break
            if counter > 1000:
                continue

            shutil.copy2(src_path, dest_path)
            logger.info(f"Backed up {src_path.name} to {dest_path.name}")

            # Only delete originals under imports (uploads). Never delete user files
            # in the recordings root or other locations.
            if delete_original and _is_under_imports(src_path):
                try:
                    src_path.unlink()
                    logger.info(f"Deleted original: {src_path}")
                except OSError as e:
                    if e.errno == 30:  # Read-only file system
                        logger.warning(
                            f"Original not removed (read-only filesystem): {src_path}"
                        )
                    else:
                        logger.warning(f"Could not remove original {src_path}: {e}")
            elif delete_original and not _is_under_imports(src_path):
                logger.info("Left original in place (outside imports): %s", src_path)

            backup_paths.append(dest_path)

        except Exception as e:
            log_error(
                "AUDIO_BACKUP",
                f"Failed to backup {src_path.name}: {e}",
                exception=e,
            )
            logger.warning(f"Backup failed for {src_path.name}: {e}")

    return backup_paths
