"""Audio utilities module."""

import shutil
import zipfile
import warnings
from pathlib import Path
from typing import Callable, Optional, Tuple, List
from datetime import datetime

try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError, CouldntEncodeError

    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    AudioSegment = None
    CouldntDecodeError = Exception
    CouldntEncodeError = Exception

try:
    # Suppress pkg_resources deprecation warning from webrtcvad
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, message=".*pkg_resources.*")
        import webrtcvad

    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    webrtcvad = None

try:
    import pyloudnorm as pyln

    PYLoudnorm_AVAILABLE = True
except ImportError:
    PYLoudnorm_AVAILABLE = False
    pyln = None

try:
    import noisereduce as nr

    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False
    nr = None

try:
    import soundfile as sf

    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False
    sf = None

from transcriptx.core.utils.logger import get_logger, log_error
from transcriptx.core.utils.paths import WAV_STORAGE_DIR
from rich.console import Console

logger = get_logger()
console = Console()

# Cache for ffmpeg path to avoid repeated lookups
_FFMPEG_PATH_CACHE: str | None = None


def backup_wav_after_processing(
    wav_path: Path,
    mp3_path: Optional[Path] = None,
    target_name: Optional[str] = None,
    delete_original: bool = True,
    file_entity_id: Optional[int] = None,
    pipeline_run_id: Optional[str] = None,
) -> Optional[Path]:
    """
    Centralized function to backup WAV files after processing.

    Determines the backup filename from:
    1. target_name if provided (explicit name)
    2. mp3_path.stem if mp3_path is provided (use MP3 name)
    3. wav_path.stem if neither provided (use original WAV name)

    Args:
        wav_path: Path to the WAV file to backup
        mp3_path: Optional path to corresponding MP3 file (used to derive backup name)
        target_name: Optional explicit target name for backup (without extension)
        delete_original: If True, delete original WAV file after backup (default: True)

    Returns:
        Path to backup file if successful, None on failure
    """
    try:
        if not wav_path.exists():
            logger.warning(f"WAV file not found, skipping backup: {wav_path}")
            return None

        # Determine target name for backup
        if target_name:
            backup_name = target_name
        elif mp3_path and mp3_path.exists():
            backup_name = mp3_path.stem
        else:
            backup_name = wav_path.stem

        # Use data/wav directory for wav storage
        wav_storage_dir = Path(WAV_STORAGE_DIR)
        wav_storage_dir.mkdir(parents=True, exist_ok=True)

        # Determine destination path for WAV file
        wav_dest_path = wav_storage_dir / f"{backup_name}.wav"

        # Handle filename conflicts in destination
        counter = 1
        while wav_dest_path.exists():
            wav_dest_path = wav_storage_dir / f"{backup_name}_{counter}.wav"
            counter += 1

        # Copy WAV file to storage directory
        shutil.copy2(wav_path, wav_dest_path)
        logger.info(
            f"Backed up {wav_path.name} to {wav_dest_path.name} (target: {backup_name})"
        )

        # Track backup in database
        if file_entity_id:
            try:
                from transcriptx.database import get_session, FileTrackingService
                from datetime import datetime

                session = get_session()
                tracking_service = FileTrackingService(session)

                # Find source artifact
                source_artifact = tracking_service.artifact_repo.find_by_path(
                    str(wav_path.resolve())
                )
                if not source_artifact:
                    # Try to find current artifact for this entity
                    current_artifacts = tracking_service.get_current_artifacts(
                        file_entity_id
                    )
                    for artifact in current_artifacts:
                        if (
                            artifact.role in ("original", "processed_wav")
                            and artifact.is_present
                        ):
                            source_artifact = artifact
                            break

                if source_artifact:
                    # Get backup file stats
                    stat = wav_dest_path.stat()
                    size_bytes = stat.st_size
                    mtime = datetime.fromtimestamp(stat.st_mtime)

                    # Create backup artifact
                    backup_artifact = tracking_service.create_artifact(
                        file_entity_id=file_entity_id,
                        path=str(wav_dest_path.resolve()),
                        file_type="wav",
                        role="backup",
                        size_bytes=size_bytes,
                        mtime=mtime,
                        is_current=False,  # Backups are not current
                        is_present=True,
                    )

                    # Log backup event
                    tracking_service.log_backup(
                        file_entity_id=file_entity_id,
                        source_artifact_id=source_artifact.id,
                        target_artifact_id=backup_artifact.id,
                        pipeline_run_id=pipeline_run_id,
                    )

                    session.commit()
                    logger.debug(
                        f"✅ Tracked backup: entity_id={file_entity_id}, backup_artifact_id={backup_artifact.id}"
                    )
            except Exception as tracking_error:
                session.rollback()
                logger.warning(
                    f"Backup tracking failed (non-critical): {tracking_error}"
                )
                # Continue even if tracking fails

        # Delete original WAV file if requested
        if delete_original:
            wav_path.unlink()
            logger.info(f"Deleted original WAV file: {wav_path}")

            # Update artifact is_present flag if tracking
            if file_entity_id:
                try:
                    from transcriptx.database import get_session, FileTrackingService

                    session = get_session()
                    tracking_service = FileTrackingService(session)

                    source_artifact = tracking_service.artifact_repo.find_by_path(
                        str(wav_path.resolve())
                    )
                    if source_artifact:
                        source_artifact.is_present = False
                        session.commit()
                except Exception:
                    session.rollback()
                    # Non-critical, continue

        return wav_dest_path

    except Exception as e:
        # Log error but don't fail
        error_msg = f"Failed to backup WAV file {wav_path.name}: {str(e)}"
        log_error("WAV_BACKUP", error_msg, exception=e)
        logger.warning(error_msg)
        return None


def backup_wav_files_after_processing(
    wav_mp3_pairs: list[tuple[Path, Optional[Path], Optional[str]]],
    delete_original: bool = True,
) -> list[Path]:
    """
    Backup multiple WAV files after processing (batch operation).

    Args:
        wav_mp3_pairs: List of tuples (wav_path, mp3_path, target_name)
                       - wav_path: Path to WAV file (required)
                       - mp3_path: Optional path to corresponding MP3 file
                       - target_name: Optional explicit target name
        delete_original: If True, delete original WAV files after backup (default: True)

    Returns:
        list[Path]: List of backup file paths (in wav storage directory)
    """
    backup_paths = []

    for pair in wav_mp3_pairs:
        if len(pair) == 3:
            wav_path, mp3_path, target_name = pair
        elif len(pair) == 2:
            wav_path, mp3_path = pair
            target_name = None
        else:
            logger.warning(f"Invalid pair format, skipping: {pair}")
            continue

        backup_path = backup_wav_after_processing(
            wav_path,
            mp3_path=mp3_path,
            target_name=target_name,
            delete_original=delete_original,
        )
        if backup_path:
            backup_paths.append(backup_path)

    return backup_paths


def get_mp3_name_for_wav_backup(wav_path: Path) -> Optional[str]:
    """
    Get MP3 name from processing state for WAV backup.

    Looks up the processing state to find the corresponding MP3 path for a WAV file,
    and returns the MP3 stem name (without extension) to use as backup target name.
    This handles cases where MP3 files were renamed.

    Args:
        wav_path: Path to the WAV file

    Returns:
        MP3 stem name (without extension) if found, None otherwise
    """
    try:
        from transcriptx.cli.processing_state import load_processing_state

        state = load_processing_state()
        processed_files = state.get("processed_files", {})

        wav_key = str(wav_path.resolve())

        # Search for entry by audio_path
        for key, entry in processed_files.items():
            entry_audio_path = entry.get("audio_path", "")
            if entry_audio_path == wav_key:
                mp3_path_str = entry.get("mp3_path")
                if mp3_path_str:
                    mp3_path = Path(mp3_path_str)
                    if mp3_path.exists():
                        return mp3_path.stem
                break

        # Also check by filename (for portability)
        filename = wav_path.name
        for key, entry in processed_files.items():
            entry_audio_path = entry.get("audio_path", "")
            if entry_audio_path and Path(entry_audio_path).name == filename:
                mp3_path_str = entry.get("mp3_path")
                if mp3_path_str:
                    mp3_path = Path(mp3_path_str)
                    if mp3_path.exists():
                        return mp3_path.stem
                break

        return None

    except Exception as e:
        log_error(
            "WAV_BACKUP",
            f"Error getting MP3 name for WAV backup {wav_path}: {e}",
            exception=e,
        )
        return None


def check_wav_backup_exists(
    wav_path: Path, mp3_path: Optional[Path] = None, target_name: Optional[str] = None
) -> Optional[Path]:
    """
    Check if a WAV file has already been backed up to storage.

    Determines the expected backup name using the same logic as backup_wav_after_processing,
    then checks if that backup file exists in the WAV storage directory.

    Args:
        wav_path: Path to the WAV file
        mp3_path: Optional path to corresponding MP3 file (used to derive backup name)
        target_name: Optional explicit target name for backup (without extension)

    Returns:
        Path to existing backup file if found, None otherwise
    """
    try:
        # Determine expected backup name (same logic as backup_wav_after_processing)
        if target_name:
            backup_name = target_name
        elif mp3_path and mp3_path.exists():
            backup_name = mp3_path.stem
        else:
            backup_name = wav_path.stem

        # Check in WAV storage directory
        wav_storage_dir = Path(WAV_STORAGE_DIR)
        if not wav_storage_dir.exists():
            return None

        # Check for exact match first
        backup_path = wav_storage_dir / f"{backup_name}.wav"
        if backup_path.exists():
            return backup_path

        # Check for numbered variants (backup_name_1.wav, backup_name_2.wav, etc.)
        counter = 1
        while True:
            backup_path = wav_storage_dir / f"{backup_name}_{counter}.wav"
            if backup_path.exists():
                return backup_path
            # Stop after checking a reasonable number of variants
            if counter > 100:
                break
            counter += 1

        return None

    except Exception as e:
        log_error(
            "WAV_BACKUP", f"Error checking WAV backup for {wav_path}: {e}", exception=e
        )
        return None


def move_wav_to_storage(wav_path: Path) -> bool:
    """
    Move a WAV file to storage directory and delete the original.

    This function uses the centralized backup_wav_after_processing() function
    for backward compatibility.

    Args:
        wav_path: Path to the WAV file to move

    Returns:
        bool: True if successful, False otherwise
    """
    backup_path = backup_wav_after_processing(
        wav_path, mp3_path=None, target_name=None, delete_original=True
    )
    return backup_path is not None


def backup_wav_files_to_storage(
    wav_paths: list[Path], base_name: Optional[str] = None
) -> list[Path]:
    """
    Backup multiple WAV files to storage directory and delete originals.

    Moves (copies then deletes) WAV files to the wav storage directory.
    This is used before merging files to preserve originals.

    This function uses the centralized backup_wav_files_after_processing() function
    for backward compatibility.

    Args:
        wav_paths: List of paths to WAV files to backup
        base_name: Optional base name for numbered backups (e.g., "260108_CSE_pen"
                   will create "260108_CSE_pen_1.wav", "260108_CSE_pen_2.wav", etc.)
                   If None, uses original filenames (backward compatible)

    Returns:
        list[Path]: List of backup file paths (in wav storage directory)
    """
    # Convert to format expected by centralized function
    wav_mp3_pairs: list[tuple[Path, Optional[Path], Optional[str]]]
    if base_name:
        # Generate numbered target names for each file
        wav_mp3_pairs = [
            (wav_path, None, f"{base_name}_{idx + 1}")
            for idx, wav_path in enumerate(wav_paths)
        ]
    else:
        # Use original filenames (backward compatible)
        wav_mp3_pairs = [(wav_path, None, None) for wav_path in wav_paths]

    return backup_wav_files_after_processing(wav_mp3_pairs, delete_original=True)


def _extract_date_from_file(wav_path: Path) -> Optional[str]:
    """
    Extract YYMMDD date from WAV file (from filename or modification time).

    Args:
        wav_path: Path to WAV file

    Returns:
        YYMMDD string (e.g., "251230") or None if extraction fails
    """
    try:
        # Lazy import to avoid circular dependency
        from transcriptx.core.utils.file_rename import extract_date_prefix

        # Use extract_date_prefix which returns YYMMDD_ format
        date_prefix = extract_date_prefix(wav_path)
        if date_prefix:
            # Remove trailing underscore to get YYMMDD
            return date_prefix.rstrip("_")

        # Fallback to modification time
        if wav_path.exists():
            mtime = wav_path.stat().st_mtime
            dt = datetime.fromtimestamp(mtime)
            return dt.strftime("%y%m%d")

        return None
    except Exception as e:
        log_error(
            "WAV_COMPRESS", f"Error extracting date from {wav_path}: {e}", exception=e
        )
        return None


def compress_wav_backups(
    delete_originals: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Tuple[List[Path], int, int]:
    """
    Compress WAV files in data/backups/wav into zip archives with maximum compression.

    Files are sorted chronologically and zipped in order. When a zip file approaches
    1GB, a new zip file is started. Zip files are named YYMMDD-YYMMDD.zip where the
    dates represent the oldest and newest files in that zip.

    Args:
        delete_originals: If True, delete original WAV files after successful compression
        progress_callback: Optional callback function(current, total, message)

    Returns:
        Tuple of (list of created zip paths, number of files compressed, number of zip files created)
    """
    wav_storage_dir = Path(WAV_STORAGE_DIR)

    if not wav_storage_dir.exists():
        logger.warning(f"WAV storage directory does not exist: {wav_storage_dir}")
        return [], 0, 0

    # Find all .wav files (exclude .zip files and other extensions)
    wav_files = [
        f
        for f in wav_storage_dir.iterdir()
        if f.is_file() and f.suffix.lower() == ".wav"
    ]

    if not wav_files:
        logger.info("No WAV files found to compress")
        return [], 0, 0

    # Sort files chronologically by date
    # Create list of (file_path, date_string) tuples for sorting
    file_dates = []
    for wav_file in wav_files:
        date_str = _extract_date_from_file(wav_file)
        if date_str:
            file_dates.append((wav_file, date_str))
        else:
            # If date extraction fails, use modification time as fallback
            try:
                mtime = wav_file.stat().st_mtime
                dt = datetime.fromtimestamp(mtime)
                date_str = dt.strftime("%y%m%d")
                file_dates.append((wav_file, date_str))
            except Exception as e:
                log_error(
                    "WAV_COMPRESS",
                    f"Error getting date for {wav_file}: {e}",
                    exception=e,
                )
                # Use current date as last resort
                date_str = datetime.now().strftime("%y%m%d")
                file_dates.append((wav_file, date_str))

    # Sort by date string (which will sort chronologically)
    file_dates.sort(key=lambda x: x[1])

    # Calculate total size for performance tracking
    total_size_mb = sum(f[0].stat().st_size for f in file_dates) / (1024 * 1024)
    total_files = len(file_dates)

    # Constants for zip file size management
    MAX_ZIP_SIZE = 1024 * 1024 * 1024  # 1GB in bytes
    ZIP_SIZE_THRESHOLD = int(MAX_ZIP_SIZE * 0.95)  # 950MB threshold

    # Wrap compression with performance logging
    file_name = f"{total_files}_files" if total_files > 0 else "compression"
    from transcriptx.core.utils.performance_logger import TimedJob

    with TimedJob("audio.compress.wav", file_name) as job:
        job.add_metadata(
            {
                "total_files": total_files,
                "total_size_mb": round(total_size_mb, 2),
                "delete_originals": delete_originals,
            }
        )

        created_zips = []
        files_compressed = 0
        current_zip: Optional[zipfile.ZipFile] = None
        current_zip_path: Optional[Path] = None
        current_zip_size = 0
        oldest_date: Optional[str] = None
        newest_date: Optional[str] = None

        try:
            for idx, (wav_file, date_str) in enumerate(file_dates):
                file_size = wav_file.stat().st_size

                # Estimate compressed size (WAV files typically compress to 10-20% of original)
                # Use 30% as a conservative estimate to account for zip overhead
                estimated_compressed_size = int(file_size * 0.3)

                # Check if we need to start a new zip file
                # Check both estimated size and actual current size
                if current_zip is None or (
                    current_zip_size + estimated_compressed_size > ZIP_SIZE_THRESHOLD
                    and current_zip_size > 0
                ):

                    # Close current zip if open and rename to reflect actual date range
                    if current_zip is not None:
                        current_zip.close()

                        # Rename zip file to reflect actual date range if it changed
                        if oldest_date and newest_date and current_zip_path:
                            expected_name = f"{oldest_date}-{newest_date}.zip"
                            if current_zip_path.name != expected_name:
                                new_zip_path = wav_storage_dir / expected_name
                                # Handle conflicts
                                counter = 1
                                while new_zip_path.exists():
                                    new_zip_path = (
                                        wav_storage_dir
                                        / f"{oldest_date}-{newest_date}_{counter}.zip"
                                    )
                                    counter += 1
                                try:
                                    current_zip_path.rename(new_zip_path)
                                    current_zip_path = new_zip_path
                                    # Update the path in created_zips list
                                    if (
                                        created_zips
                                        and created_zips[-1] != current_zip_path
                                    ):
                                        created_zips[-1] = current_zip_path
                                except Exception as e:
                                    logger.warning(
                                        f"Could not rename zip to reflect date range: {e}"
                                    )

                        logger.info(
                            f"Created zip: {current_zip_path.name} ({current_zip_size / (1024*1024):.1f} MB)"
                        )

                    # Generate new zip filename (will be updated when closing if date range expands)
                    zip_name = f"{date_str}-{date_str}.zip"
                    current_zip_path = wav_storage_dir / zip_name

                    # Handle filename conflicts
                    counter = 1
                    while current_zip_path.exists():
                        zip_name = f"{date_str}-{date_str}_{counter}.zip"
                        current_zip_path = wav_storage_dir / zip_name
                        counter += 1

                    # Open new zip file with maximum compression
                    current_zip = zipfile.ZipFile(
                        current_zip_path,
                        "w",
                        compression=zipfile.ZIP_DEFLATED,
                        compresslevel=9,
                    )

                    created_zips.append(current_zip_path)
                    current_zip_size = 0
                    oldest_date = date_str
                    newest_date = date_str

                # Update date range for current zip
                if oldest_date is None or date_str < oldest_date:
                    oldest_date = date_str
                if newest_date is None or date_str > newest_date:
                    newest_date = date_str

                # Add file to zip
                try:
                    current_zip.write(wav_file, arcname=wav_file.name)
                    # Update size from actual file on disk (zipfile should flush on write)
                    current_zip_size = current_zip_path.stat().st_size
                    files_compressed += 1

                    if progress_callback:
                        progress_callback(
                            idx + 1, total_files, f"Compressed {wav_file.name}"
                        )

                except Exception as e:
                    error_msg = f"Error adding {wav_file.name} to zip: {e}"
                    log_error("WAV_COMPRESS", error_msg, exception=e)
                    logger.warning(error_msg)

            # Close final zip file and rename to reflect actual date range
            if current_zip is not None:
                current_zip.close()

                # Rename zip file to reflect actual date range if it changed
                if oldest_date and newest_date and current_zip_path:
                    expected_name = f"{oldest_date}-{newest_date}.zip"
                    if current_zip_path.name != expected_name:
                        new_zip_path = wav_storage_dir / expected_name
                        # Handle conflicts
                        counter = 1
                        while new_zip_path.exists():
                            new_zip_path = (
                                wav_storage_dir
                                / f"{oldest_date}-{newest_date}_{counter}.zip"
                            )
                            counter += 1
                        try:
                            current_zip_path.rename(new_zip_path)
                            current_zip_path = new_zip_path
                            # Update the path in created_zips list
                            if created_zips and created_zips[-1] != current_zip_path:
                                created_zips[-1] = current_zip_path
                        except Exception as e:
                            logger.warning(
                                f"Could not rename zip to reflect date range: {e}"
                            )

                logger.info(
                    f"Created zip: {current_zip_path.name} ({current_zip_size / (1024*1024):.1f} MB)"
                )

            # Optionally delete original WAV files
            if delete_originals and files_compressed > 0:
                deleted_count = 0
                for wav_file, _ in file_dates:
                    try:
                        if wav_file.exists():
                            wav_file.unlink()
                            deleted_count += 1
                    except Exception as e:
                        error_msg = f"Error deleting {wav_file.name}: {e}"
                        log_error("WAV_COMPRESS", error_msg, exception=e)
                        logger.warning(error_msg)

                logger.info(
                    f"Deleted {deleted_count} original WAV files after compression"
                )

            # Update metadata with final results
            job.add_metadata(
                {"zip_count": len(created_zips), "files_compressed": files_compressed}
            )

            return created_zips, files_compressed, len(created_zips)

        except Exception as e:
            error_msg = f"Error during WAV compression: {e}"
            log_error("WAV_COMPRESS", error_msg, exception=e)

            # Close any open zip file
            if current_zip is not None:
                try:
                    current_zip.close()
                except:
                    pass

            raise RuntimeError(error_msg)
