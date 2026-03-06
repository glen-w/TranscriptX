"""Audio utilities module."""

import subprocess
import shutil
import os
import warnings

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
        warnings.filterwarnings(
            "ignore", category=UserWarning, message=".*pkg_resources.*"
        )
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

from transcriptx.core.utils.logger import get_logger
from rich.console import Console

logger = get_logger()
console = Console()

# Cache for ffmpeg path to avoid repeated lookups
_FFMPEG_PATH_CACHE: str | None = None


def _find_ffmpeg_path() -> str | None:
    """
    Find ffmpeg executable path.

    Returns:
        str | None: Path to ffmpeg executable, or None if not found
    """
    global _FFMPEG_PATH_CACHE

    # Return cached path if available
    if _FFMPEG_PATH_CACHE is not None:
        return _FFMPEG_PATH_CACHE

    # Try to find ffmpeg in PATH first
    ffmpeg_path = shutil.which("ffmpeg")

    # If not in PATH, try common installation paths
    if not ffmpeg_path:
        common_paths = [
            "/opt/homebrew/bin/ffmpeg",  # Homebrew on Apple Silicon
            "/usr/local/bin/ffmpeg",  # Homebrew on Intel Mac
            "/usr/bin/ffmpeg",  # System installation
        ]
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                ffmpeg_path = path
                break

    # Cache the result
    _FFMPEG_PATH_CACHE = ffmpeg_path

    # Configure pydub to use the found ffmpeg path
    if ffmpeg_path and PYDUB_AVAILABLE:
        # Configure pydub's converter to use the full path to ffmpeg
        AudioSegment.converter = ffmpeg_path

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
        else:
            return False, f"ffmpeg command failed (exit code: {result.returncode})"
    except subprocess.TimeoutExpired:
        return False, "ffmpeg check timed out"
    except Exception as e:
        return False, f"Error checking ffmpeg: {str(e)}"


def check_ffplay_available() -> tuple[bool, str | None]:
    """
    Check if ffplay is available on the system.

    Returns:
        tuple[bool, str | None]: (is_available, error_message)
    """
    # Try to find ffplay in PATH first
    ffplay_path = shutil.which("ffplay")

    # If not in PATH, try common installation paths
    if not ffplay_path:
        common_paths = [
            "/opt/homebrew/bin/ffplay",  # Homebrew on Apple Silicon
            "/usr/local/bin/ffplay",  # Homebrew on Intel Mac
            "/usr/bin/ffplay",  # System installation
        ]
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                ffplay_path = path
                break

    if not ffplay_path:
        return False, "ffplay is not installed or not in PATH"

    try:
        result = subprocess.run(
            [ffplay_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return True, None
        else:
            return False, f"ffplay command failed (exit code: {result.returncode})"
    except subprocess.TimeoutExpired:
        return False, "ffplay check timed out"
    except Exception as e:
        return False, f"Error checking ffplay: {str(e)}"
