"""Fast PCM WAV slicing utilities."""

from __future__ import annotations

import wave
from pathlib import Path

from transcriptx.core.utils.logger import get_logger

logger = get_logger()


def slice_wav_pcm(
    pcm_path: Path,
    start_s: float,
    duration_s: float,
    output_path: Path,
) -> bool:
    """Slice a PCM WAV file using the standard library (no ffmpeg)."""
    if not pcm_path.exists():
        logger.warning(f"PCM file does not exist: {pcm_path}")
        return False

    try:
        with wave.open(str(pcm_path), "rb") as infile:
            sample_rate = infile.getframerate()
            channels = infile.getnchannels()
            sampwidth = infile.getsampwidth()
            nframes = infile.getnframes()

            if sample_rate <= 0 or nframes <= 0:
                logger.warning(f"Invalid PCM metadata: {pcm_path}")
                return False

            start_frame = max(0, int(start_s * sample_rate))
            end_frame = min(nframes, start_frame + int(duration_s * sample_rate))
            if end_frame <= start_frame:
                logger.warning(
                    f"Invalid slice range: {start_frame}-{end_frame} for {pcm_path}"
                )
                return False

            infile.setpos(start_frame)
            frames_to_read = end_frame - start_frame
            frames = infile.readframes(frames_to_read)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output_path), "wb") as outfile:
                outfile.setnchannels(channels)
                outfile.setsampwidth(sampwidth)
                outfile.setframerate(sample_rate)
                outfile.writeframes(frames)

        return output_path.exists() and output_path.stat().st_size > 0
    except wave.Error as exc:
        logger.warning(f"WAV slicing failed for {pcm_path}: {exc}")
        return False
    except OSError as exc:
        logger.warning(f"WAV slicing error for {pcm_path}: {exc}")
        return False
