"""
Pure ffmpeg availability helpers — no CLI or UI concerns.

Both the CLI and app layers import from here.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import warnings

try:
    from pydub import AudioSegment

    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    AudioSegment = None  # type: ignore[assignment,misc]

try:
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore", category=UserWarning, message=".*pkg_resources.*"
        )
        import webrtcvad  # noqa: F401

    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False

try:
    import pyloudnorm  # noqa: F401

    PYLoudnorm_AVAILABLE = True
except ImportError:
    PYLoudnorm_AVAILABLE = False

try:
    import noisereduce  # noqa: F401

    NOISEREDUCE_AVAILABLE = True
except ImportError:
    NOISEREDUCE_AVAILABLE = False

try:
    import soundfile  # noqa: F401

    SOUNDFILE_AVAILABLE = True
except ImportError:
    SOUNDFILE_AVAILABLE = False

# Cache for ffmpeg path to avoid repeated lookups
_FFMPEG_PATH_CACHE: str | None = None


def _find_ffmpeg_path() -> str | None:
    """Find ffmpeg executable path, caching the result."""
    global _FFMPEG_PATH_CACHE

    if _FFMPEG_PATH_CACHE is not None:
        return _FFMPEG_PATH_CACHE

    ffmpeg_path = shutil.which("ffmpeg")

    if not ffmpeg_path:
        common_paths = [
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/usr/bin/ffmpeg",
        ]
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                ffmpeg_path = path
                break

    _FFMPEG_PATH_CACHE = ffmpeg_path

    if ffmpeg_path and PYDUB_AVAILABLE and AudioSegment is not None:
        AudioSegment.converter = ffmpeg_path  # type: ignore[union-attr]

    return ffmpeg_path


def check_ffmpeg_available() -> tuple[bool, str | None]:
    """
    Check if ffmpeg is available on the system.

    Returns:
        tuple[bool, str | None]: (is_available, error_message)
    """
    ffmpeg_path = _find_ffmpeg_path()

    if not ffmpeg_path:
        return False, "ffmpeg is not installed or not in PATH"

    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return True, None
        return False, f"ffmpeg command failed (exit code: {result.returncode})"
    except subprocess.TimeoutExpired:
        return False, "ffmpeg check timed out"
    except Exception as e:
        return False, f"Error checking ffmpeg: {str(e)}"
