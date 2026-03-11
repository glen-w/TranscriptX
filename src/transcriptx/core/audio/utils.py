"""Audio utilities — duration probing and other lightweight helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

try:
    from pydub import AudioSegment

    _PYDUB_AVAILABLE = True
except ImportError:
    _PYDUB_AVAILABLE = False
    AudioSegment = None  # type: ignore[assignment,misc]


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
            audio = AudioSegment.from_file(str(path))
            return len(audio) / 1000.0
        except Exception:
            pass

    return None
