"""
Shim: ffmpeg tool helpers have moved to core.audio.tools.

Kept for one release cycle so direct imports continue to work.
Import from transcriptx.core.audio.tools instead.
"""

import shutil

from transcriptx.core.audio.tools import (  # noqa: F401
    _find_ffmpeg_path,
    check_ffmpeg_available,
    PYDUB_AVAILABLE,
    WEBRTCVAD_AVAILABLE,
    PYLoudnorm_AVAILABLE,
    NOISEREDUCE_AVAILABLE,
    SOUNDFILE_AVAILABLE,
)


def check_ffplay_available() -> tuple[bool, str | None]:
    """Check if ffplay is available on the system."""
    import subprocess

    ffplay_path = shutil.which("ffplay")

    if not ffplay_path:
        common_paths = [
            "/opt/homebrew/bin/ffplay",
            "/usr/local/bin/ffplay",
            "/usr/bin/ffplay",
        ]
        import os

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
        return False, f"ffplay command failed (exit code: {result.returncode})"
    except subprocess.TimeoutExpired:
        return False, "ffplay check timed out"
    except Exception as e:
        return False, f"Error checking ffplay: {str(e)}"
