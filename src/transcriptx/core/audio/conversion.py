"""
Pure audio merge/conversion helpers — no UI or presentation logic.

App and web layers import from here.
"""

from __future__ import annotations

import subprocess
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
from transcriptx.core.audio.tools import _find_ffmpeg_path, check_ffmpeg_available
from transcriptx.core.utils.logger import get_logger, log_error

logger = get_logger()


def export_mp3_for_transcription(
    input_path: Path,
    output_path: Path,
    *,
    codec: str = "libmp3lame",
    bitrate: str = "128k",
    channels: int = 2,
    sample_rate: int = 0,
    force_reencode: bool = False,
) -> Path:
    """
    Export audio to stereo MP3 for transcription staging.

    When input is already MP3 and force_reencode is False, returns the original
    input path without creating a new file.

    Raises:
        FileNotFoundError: input missing
        ValueError: ffmpeg unavailable
        RuntimeError: ffmpeg export failed
    """
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {input_path}")

    if input_path.suffix.lower() == ".mp3" and not force_reencode:
        return input_path

    ffmpeg_ok, ffmpeg_err = check_ffmpeg_available()
    if not ffmpeg_ok:
        raise ValueError(
            f"ffmpeg is required for transcription conversion. {ffmpeg_err}"
        )

    ffmpeg_path = _find_ffmpeg_path()
    if not ffmpeg_path:
        raise ValueError("ffmpeg executable not found")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),
        "-codec:a",
        codec,
        "-b:a",
        bitrate,
        "-ac",
        str(channels),
    ]
    if sample_rate > 0:
        cmd.extend(["-ar", str(sample_rate)])
    cmd.append(str(output_path))

    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-20:])
        raise RuntimeError(
            f"ffmpeg failed to export MP3 (exit {result.returncode}): {stderr_tail}"
        )

    return output_path


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
