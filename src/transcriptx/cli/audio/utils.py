"""Audio utilities module."""

import subprocess
import warnings
from pathlib import Path

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


def get_audio_duration(audio_path: Path) -> float | None:
    """
    Get audio duration in seconds using pydub or ffprobe.

    Args:
        audio_path: Path to the audio file

    Returns:
        float: Duration in seconds, or None if unavailable
    """
    if not audio_path.exists():
        return None

    # Try ffprobe first (fast metadata read)
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
                str(audio_path),
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

    # Fallback to pydub (decodes full file)
    if PYDUB_AVAILABLE:
        try:
            audio = AudioSegment.from_file(str(audio_path))
            return len(audio) / 1000.0  # pydub returns duration in milliseconds
        except Exception:
            pass

    return None
