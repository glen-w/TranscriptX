"""
Pure audio merge/conversion helpers — no CLI or UI concerns.

Both the CLI and app layers import from here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, List, Optional

try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError, CouldntEncodeError

    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    AudioSegment = None  # type: ignore[assignment,misc]
    CouldntDecodeError = Exception  # type: ignore[assignment,misc]
    CouldntEncodeError = Exception  # type: ignore[assignment,misc]

from transcriptx.core.audio.preprocessing import apply_preprocessing
from transcriptx.core.audio.tools import check_ffmpeg_available
from transcriptx.core.utils.logger import get_logger, log_error

logger = get_logger()


def merge_audio_files(
    audio_paths: list[Path],
    output_path: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    bitrate: str = "192k",
    apply_preprocessing_steps: bool = True,
    config: Any = None,
) -> Path:
    """
    Merge multiple audio files (WAV, MP3, OGG, etc.) into a single MP3 file.

    Args:
        audio_paths: List of paths to audio files to merge, in order.
        output_path: Destination path for the output MP3 file.
        progress_callback: Optional callback(current, total, message).
        bitrate: MP3 bitrate (default "192k").
        apply_preprocessing_steps: Whether to run preprocessing on each segment.
        config: Optional AudioPreprocessingConfig.

    Returns:
        Path to the created merged MP3 file.

    Raises:
        ValueError: pydub not available, ffmpeg missing, or no files provided.
        FileNotFoundError: Any input path does not exist.
        RuntimeError: Merge or export failed.
    """
    if not PYDUB_AVAILABLE:
        raise ValueError("pydub is not installed. Install it with: pip install pydub")

    ffmpeg_available, error_msg = check_ffmpeg_available()
    if not ffmpeg_available:
        raise ValueError(f"ffmpeg is required for audio merging. {error_msg}")

    if not audio_paths:
        raise ValueError("No audio files provided for merging")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    for path in audio_paths:
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

    try:
        merged_audio: Optional[AudioSegment] = None
        total_files = len(audio_paths)
        all_applied_steps: List[str] = []

        for idx, path in enumerate(audio_paths):
            if progress_callback:
                progress_callback(
                    idx,
                    total_files,
                    f"Loading {path.name} ({idx + 1}/{total_files})...",
                )

            audio = AudioSegment.from_file(str(path))  # type: ignore[union-attr]

            if apply_preprocessing_steps:
                audio, applied_steps = apply_preprocessing(audio, config, None)
                if applied_steps:
                    all_applied_steps.extend(applied_steps)

            if merged_audio is None:
                merged_audio = audio
            else:
                merged_audio += audio

        if progress_callback:
            progress_callback(total_files - 1, total_files, "Exporting merged MP3...")

        if merged_audio is not None:
            merged_audio.export(str(output_path), format="mp3", bitrate=bitrate)  # type: ignore[union-attr]
        else:
            raise RuntimeError("No audio to export after merging")

        if progress_callback:
            progress_callback(
                total_files, total_files, f"Completed: {output_path.name}"
            )

        logger.info(f"Merged {total_files} audio files into {output_path.name}")
        return output_path

    except CouldntDecodeError as e:
        msg = f"Could not decode one of the audio files: {e}"
        log_error("AUDIO_MERGE", msg, exception=e)
        raise RuntimeError(msg)
    except CouldntEncodeError as e:
        msg = f"Could not encode merged MP3 file: {e}"
        log_error("AUDIO_MERGE", msg, exception=e)
        raise RuntimeError(msg)
    except Exception as e:
        msg = f"Error merging audio files: {e}"
        log_error("AUDIO_MERGE", msg, exception=e)
        raise RuntimeError(msg)


def merge_wav_files(
    wav_paths: list[Path],
    output_path: Path,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    bitrate: str = "192k",
    apply_preprocessing_steps: bool = True,
    config: Any = None,
) -> Path:
    """Merge multiple WAV files into a single MP3. Delegates to merge_audio_files."""
    return merge_audio_files(
        wav_paths,
        output_path,
        progress_callback=progress_callback,
        bitrate=bitrate,
        apply_preprocessing_steps=apply_preprocessing_steps,
        config=config,
    )
