import os
from pathlib import Path

# Get the project root directory (where this file is located, go up to transcriptx root)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

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

def ensure_data_dirs() -> None:
    """Create core data directories if they do not exist."""
    Path(RECORDINGS_DIR).mkdir(parents=True, exist_ok=True)
    Path(DIARISED_TRANSCRIPTS_DIR).mkdir(parents=True, exist_ok=True)
    Path(WAV_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
    Path(PREPROCESSING_DIR).mkdir(parents=True, exist_ok=True)
    Path(AUDIO_PLAYBACK_CACHE_DIR).mkdir(parents=True, exist_ok=True)
    Path(GROUP_OUTPUTS_DIR).mkdir(parents=True, exist_ok=True)
