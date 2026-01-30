"""Audio utilities module."""

import warnings
from pathlib import Path
from typing import Callable, Optional, List, Dict, Any

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
from rich.console import Console

logger = get_logger()
console = Console()

# Cache for ffmpeg path to avoid repeated lookups
_FFMPEG_PATH_CACHE: str | None = None


from .tools import check_ffmpeg_available
from .preprocessing import apply_preprocessing


def estimate_conversion_time(file_size_mb: float) -> float:
    """
    Estimate conversion time based on file size.

    Args:
        file_size_mb: File size in megabytes

    Returns:
        float: Estimated conversion time in seconds
    """
    # Rough estimate: ~1MB per minute for typical audio
    # Conversion is typically faster than real-time
    # Estimate: 0.5 seconds per MB (conservative)
    return file_size_mb * 0.5


def convert_wav_to_mp3(
    wav_path: Path,
    output_dir: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    bitrate: str = "192k",
    apply_preprocessing_steps: bool = True,
    config: Any = None,
    preprocessing_decisions: Dict[str, bool] | None = None,
    file_entity_id: Optional[int] = None,
    pipeline_run_id: Optional[str] = None,
) -> Path:
    """
    Convert a WAV file to MP3 format.

    Args:
        wav_path: Path to the input WAV file
        output_dir: Directory to save the output MP3 file
        progress_callback: Optional callback function(current, total, message)
        bitrate: MP3 bitrate (default: "192k")

    Returns:
        Path: Path to the created MP3 file

    Raises:
        FileNotFoundError: If WAV file doesn't exist
        ValueError: If pydub is not available or ffmpeg is missing
        RuntimeError: If conversion fails
    """
    if not PYDUB_AVAILABLE:
        raise ValueError(
            "pydub is not installed. Please install it with: pip install pydub"
        )

    # Check ffmpeg availability
    ffmpeg_available, error_msg = check_ffmpeg_available()
    if not ffmpeg_available:
        raise ValueError(f"ffmpeg is required for audio conversion. {error_msg}")

    if not wav_path.exists():
        raise FileNotFoundError(f"WAV file not found: {wav_path}")

    # Get file size for logging and estimation
    input_file_size_mb = wav_path.stat().st_size / (1024 * 1024)

    # Show time estimate
    try:
        from transcriptx.core.utils.performance_estimator import (
            PerformanceEstimator,
            format_time_estimate,
        )

        estimator = PerformanceEstimator()
        estimate = estimator.estimate_conversion_time(
            file_size_mb=input_file_size_mb, bitrate=bitrate
        )
        if estimate.get("estimated_seconds") is not None:
            estimate_str = format_time_estimate(estimate)
            logger.info(f"Estimated conversion time: {estimate_str}")
    except Exception:
        pass  # Don't fail if estimation fails

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate output filename
    output_filename = wav_path.stem + ".mp3"
    output_path = output_dir / output_filename

    # Handle filename conflicts
    counter = 1
    while output_path.exists():
        output_filename = f"{wav_path.stem}_{counter}.mp3"
        output_path = output_dir / output_filename
        counter += 1

    # Wrap conversion with performance logging
    from transcriptx.core.utils.performance_logger import TimedJob

    with TimedJob("audio.convert.wav_to_mp3", wav_path.name) as job:
        job.add_metadata(
            {"bitrate": bitrate, "input_file_size_mb": round(input_file_size_mb, 2)}
        )

        try:
            if progress_callback:
                progress_callback(0, 100, f"Loading {wav_path.name}...")

            # Load WAV file
            audio = AudioSegment.from_wav(str(wav_path))

            # Track source artifact for conversion
            source_artifact_id = None
            if file_entity_id:
                try:
                    from transcriptx.database import get_session, FileTrackingService

                    session = get_session()
                    tracking_service = FileTrackingService(session)

                    # Find source artifact (original or processed_wav)
                    source_artifact = tracking_service.artifact_repo.find_by_path(
                        str(wav_path.resolve())
                    )
                    if not source_artifact:
                        # Try to find current artifact for this entity
                        current_artifacts = tracking_service.get_current_artifacts(
                            file_entity_id
                        )
                        # Prefer processed_wav, fallback to original
                        for artifact in current_artifacts:
                            if artifact.role in ("processed_wav", "original"):
                                source_artifact = artifact
                                break
                    if source_artifact:
                        source_artifact_id = source_artifact.id
                except Exception as e:
                    logger.debug(f"Could not find source artifact for tracking: {e}")

            # Apply preprocessing if enabled
            applied_steps: List[str] = []
            preprocessing_summary = {}
            if apply_preprocessing_steps:
                audio, applied_steps = apply_preprocessing(
                    audio, config, progress_callback, preprocessing_decisions
                )
                if applied_steps:
                    job.add_metadata({"applied_preprocessing": applied_steps})
                    # Build preprocessing summary for tracking
                    preprocessing_summary = {
                        "denoise": "denoise" in str(applied_steps),
                        "highpass": "highpass" in str(applied_steps),
                        "lowpass": "lowpass" in str(applied_steps),
                        "bandpass": "bandpass" in str(applied_steps),
                        "normalize": "normalize" in str(applied_steps),
                        "mono": "mono" in applied_steps,
                        "resample": "resample" in str(applied_steps),
                    }

            if progress_callback:
                progress_callback(80, 100, f"Converting to MP3...")

            # Export as MP3
            audio.export(str(output_path), format="mp3", bitrate=bitrate)

            if progress_callback:
                progress_callback(100, 100, f"Completed: {output_path.name}")

            # Get output file size
            output_file_size_mb = output_path.stat().st_size / (1024 * 1024)
            job.add_metadata({"output_file_size_mb": round(output_file_size_mb, 2)})

            # Track conversion in database
            if file_entity_id and source_artifact_id:
                try:
                    from transcriptx.database import get_session, FileTrackingService
                    from datetime import datetime

                    session = get_session()
                    tracking_service = FileTrackingService(session)

                    # Get file stats
                    stat = output_path.stat()
                    size_bytes = stat.st_size
                    mtime = datetime.fromtimestamp(stat.st_mtime)

                    # Create MP3 artifact
                    mp3_artifact = tracking_service.create_artifact(
                        file_entity_id=file_entity_id,
                        path=str(output_path.resolve()),
                        file_type="mp3",
                        role="mp3",
                        size_bytes=size_bytes,
                        mtime=mtime,
                        is_current=True,
                        is_present=True,
                        metadata={"bitrate": bitrate},
                    )

                    # Build operation details
                    operation_details = {
                        "bitrate": bitrate,
                        "input_file_size_mb": round(input_file_size_mb, 2),
                        "output_file_size_mb": round(output_file_size_mb, 2),
                    }
                    if applied_steps:
                        operation_details["applied_preprocessing"] = applied_steps
                        operation_details["preprocessing_summary"] = (
                            preprocessing_summary
                        )

                    # Log conversion event
                    tracking_service.log_conversion(
                        file_entity_id=file_entity_id,
                        source_artifact_id=source_artifact_id,
                        target_artifact_id=mp3_artifact.id,
                        pipeline_run_id=pipeline_run_id,
                        operation_details=operation_details,
                    )

                    session.commit()
                    logger.debug(
                        f"✅ Tracked conversion: entity_id={file_entity_id}, mp3_artifact_id={mp3_artifact.id}"
                    )
                except Exception as tracking_error:
                    session.rollback()
                    logger.warning(
                        f"Conversion tracking failed (non-critical): {tracking_error}"
                    )
                    # Continue even if tracking fails

            logger.info(f"Converted {wav_path.name} to {output_path.name}")

            return output_path

        except CouldntDecodeError as e:
            error_msg = f"Could not decode WAV file {wav_path.name}: {str(e)}"
            log_error("AUDIO_CONVERSION", error_msg, exception=e)
            raise RuntimeError(error_msg)
        except CouldntEncodeError as e:
            error_msg = f"Could not encode MP3 file: {str(e)}"
            log_error("AUDIO_CONVERSION", error_msg, exception=e)
            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = f"Error converting {wav_path.name} to MP3: {str(e)}"
            log_error("AUDIO_CONVERSION", error_msg, exception=e)
            raise RuntimeError(error_msg)


def merge_wav_files(
    wav_paths: list[Path],
    output_path: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    bitrate: str = "192k",
    apply_preprocessing_steps: bool = True,
    config: Any = None,
) -> Path:
    """
    Merge multiple WAV files into a single MP3 file.

    Args:
        wav_paths: List of paths to WAV files to merge
        output_path: Path for the output MP3 file
        progress_callback: Optional callback function(current, total, message)
        bitrate: MP3 bitrate (default: "192k")

    Returns:
        Path: Path to the created merged MP3 file

    Raises:
        ValueError: If pydub is not available, ffmpeg is missing, or no files provided
        FileNotFoundError: If any WAV file doesn't exist
        RuntimeError: If merge fails
    """
    if not PYDUB_AVAILABLE:
        raise ValueError(
            "pydub is not installed. Please install it with: pip install pydub"
        )

    # Check ffmpeg availability
    ffmpeg_available, error_msg = check_ffmpeg_available()
    if not ffmpeg_available:
        raise ValueError(f"ffmpeg is required for audio conversion. {error_msg}")

    if not wav_paths:
        raise ValueError("No WAV files provided for merging")

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Verify all files exist
    for wav_path in wav_paths:
        if not wav_path.exists():
            raise FileNotFoundError(f"WAV file not found: {wav_path}")

    try:
        merged_audio: Optional[AudioSegment] = None
        total_files = len(wav_paths)
        all_applied_steps: List[str] = []
        for idx, wav_path in enumerate(wav_paths):
            if progress_callback:
                progress_msg = f"Loading {wav_path.name} ({idx + 1}/{total_files})..."
                progress_callback(idx, total_files, progress_msg)

            # Load WAV file
            audio = AudioSegment.from_wav(str(wav_path))

            # Apply preprocessing if enabled
            if apply_preprocessing_steps:
                audio, applied_steps = apply_preprocessing(audio, config, None)
                if applied_steps:
                    all_applied_steps.extend(applied_steps)

            # Append to merged audio
            if merged_audio is None:
                merged_audio = audio
            else:
                merged_audio += audio

        if progress_callback:
            progress_callback(total_files - 1, total_files, "Exporting merged MP3...")

        # Export merged audio as MP3
        if merged_audio is not None:
            merged_audio.export(str(output_path), format="mp3", bitrate=bitrate)
        else:
            raise RuntimeError("No audio to export after merging")

        if progress_callback:
            progress_callback(
                total_files, total_files, f"Completed: {output_path.name}"
            )

        logger.info(f"Merged {total_files} WAV files into {output_path.name}")
        return output_path

    except CouldntDecodeError as e:
        error_msg = f"Could not decode one of the WAV files: {str(e)}"
        log_error("AUDIO_MERGE", error_msg, exception=e)
        raise RuntimeError(error_msg)
    except CouldntEncodeError as e:
        error_msg = f"Could not encode merged MP3 file: {str(e)}"
        log_error("AUDIO_MERGE", error_msg, exception=e)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Error merging WAV files: {str(e)}"
        log_error("AUDIO_MERGE", error_msg, exception=e)
        raise RuntimeError(error_msg)
