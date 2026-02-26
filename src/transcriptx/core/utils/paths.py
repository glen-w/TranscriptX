import logging
import os
from pathlib import Path

# Get the project root directory (where this file is located, go up to transcriptx root)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
# Allow override for Docker/installed package: data dir outside site-packages (e.g. TRANSCRIPTX_DATA_DIR=/data)
_data_dir_env = os.getenv("TRANSCRIPTX_DATA_DIR")
DATA_DIR = Path(_data_dir_env).resolve() if _data_dir_env else (PROJECT_ROOT / "data")
# Profiles dir (default DATA_DIR/profiles). Override when DATA_DIR is read-only (e.g. web container tmpfs).
_profiles_dir_env = os.getenv("TRANSCRIPTX_PROFILES_DIR")
PROFILES_DIR = Path(_profiles_dir_env).resolve() if _profiles_dir_env else (DATA_DIR / "profiles")

RECORDINGS_DIR = str(DATA_DIR / "recordings")
READABLE_TRANSCRIPTS_DIR = str(DATA_DIR / "transcripts" / "readable")
DIARISED_TRANSCRIPTS_DIR = str(DATA_DIR / "transcripts")
_DEFAULT_OUTPUTS_DIR = str(DATA_DIR / "outputs")
# Allow tests/CI to override outputs location (e.g. tmp_path) to avoid writing into repo.
# This must be set before importing transcriptx.* modules in the process.
OUTPUTS_DIR = os.getenv("TRANSCRIPTX_OUTPUT_DIR", _DEFAULT_OUTPUTS_DIR)
GROUP_OUTPUTS_DIR = str(Path(OUTPUTS_DIR) / "groups")
WAV_OUTPUT_DIR = str(
    DATA_DIR / "recordings"
)  # Changed from outputs/recordings to recordings
WAV_STORAGE_DIR = str(DATA_DIR / "backups" / "wav")
PREPROCESSING_DIR = str(DATA_DIR / "preprocessing")
PERFORMANCE_LOGS_DIR = str(DATA_DIR)
AUDIO_PLAYBACK_CACHE_DIR = str(DATA_DIR / "cache" / "audio_playback")

_log = logging.getLogger(__name__)


def ensure_data_dirs() -> None:
    """Create core data directories if they do not exist.

    On permission errors (e.g. read-only DATA_DIR in Docker web container),
    logs a warning and continues so read-only modes (e.g. web-viewer) can start.
    """
    dirs = [
        RECORDINGS_DIR,
        DIARISED_TRANSCRIPTS_DIR,
        WAV_STORAGE_DIR,
        PREPROCESSING_DIR,
        AUDIO_PLAYBACK_CACHE_DIR,
        GROUP_OUTPUTS_DIR,
    ]
    for d in dirs:
        try:
            Path(d).mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            _log.warning(
                "Could not create data directory %s: %s (continuing; some features may be unavailable)",
                d,
                e,
            )
