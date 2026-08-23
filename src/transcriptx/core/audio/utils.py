"""Audio utilities — duration probing and other lightweight helpers."""

from __future__ import annotations

import io
import subprocess
from pathlib import Path
from typing import Optional

try:
    from pydub import AudioSegment
    from pydub.exceptions import CouldntDecodeError

    _PYDUB_AVAILABLE = True
except ImportError:
    _PYDUB_AVAILABLE = False
    AudioSegment = None  # type: ignore[assignment,misc]
    CouldntDecodeError = Exception  # type: ignore[assignment,misc]


def load_audio_segment(audio_path: Path | str) -> "AudioSegment":
    """
    Load audio via pydub, falling back to ffmpeg for compressed WAV (e.g. ADPCM IMA).

    pydub infers a raw PCM output codec from ffprobe ``bits_per_sample``. For
    ADPCM IMA WAV that value is 4, so pydub requests encoder ``pcm_s4le``, which
    ffmpeg does not provide. Decoding through ffmpeg with ``pcm_s16le`` avoids that.
    """
    if not _PYDUB_AVAILABLE or AudioSegment is None:
        raise RuntimeError("pydub is not available")

    path = Path(audio_path)
    try:
        return AudioSegment.from_file(str(path))
    except CouldntDecodeError:
        pass

    from transcriptx.core.audio.tools import _find_ffmpeg_path

    ffmpeg = _find_ffmpeg_path()
    if not ffmpeg:
        raise CouldntDecodeError("ffmpeg not available for fallback decode")

    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-f",
            "wav",
            "-",
        ],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace")
        raise CouldntDecodeError(
            f"Decoding failed. ffmpeg returned error code: {result.returncode}\n\n"
            f"Output from ffmpeg/avlib:\n\n{stderr}"
        )

    return AudioSegment.from_wav(io.BytesIO(result.stdout))


def get_audio_duration(audio_path: Path | str) -> Optional[float]:
    """
    Get audio duration in seconds using ffprobe, falling back to pydub.

    Args:
        audio_path: Path to the audio file.

    Returns:
        Duration in seconds, or None if unavailable.
    """
    path = Path(audio_path)
    if not path.exists():
        return None

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            if duration > 0:
                return duration
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass

    if _PYDUB_AVAILABLE and AudioSegment is not None:
        try:
            audio = load_audio_segment(path)
            return len(audio) / 1000.0
        except Exception:
            pass

    return None
