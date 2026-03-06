"""Path and storage roots for TranscriptX. See docs/STORAGE.md for policy."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

# Load .env early so env vars are available before path constants are computed.
from transcriptx._bootstrap import bootstrap as _bootstrap_env

_bootstrap_env()

_log = logging.getLogger(__name__)


def _env_path_value(var: str) -> Path | None:
    """Read env var as Path with expanduser (not resolve). Paths may not exist yet."""
    val = os.getenv(var)
    return Path(val).expanduser() if val else None


@dataclass(frozen=True)
class PathSettings:
    """Canonical path roots and critical shared paths. All fields are Path."""

    project_root: Path
    # Library (user-owned)
    recordings_dir: Path
    transcripts_dir: Path
    readable_transcripts_dir: Path
    # Working (app-managed)
    data_dir: Path
    outputs_dir: Path
    group_outputs_dir: Path
    preprocessing_dir: Path
    state_dir: Path
    processing_state_file: Path
    # Config
    config_dir: Path
    profiles_dir: Path
    # Backup/archive
    wav_backup_dir: Path
    state_backup_dir: Path
    # Cache
    audio_playback_cache_dir: Path
    voice_cache_dir: Path


def _build_paths() -> PathSettings:
    """Build all paths from env vars with documented defaults. Uses expanduser(), not resolve()."""
    project_root = Path(__file__).parent.parent.parent.parent.parent
    data_dir = _env_path_value("TRANSCRIPTX_DATA_DIR") or (project_root / "data")
    config_dir = _env_path_value("TRANSCRIPTX_CONFIG_DIR") or (
        project_root / ".transcriptx"
    )
    recordings_dir = _env_path_value("TRANSCRIPTX_RECORDINGS_DIR") or (
        data_dir / "recordings"
    )
    transcripts_dir = _env_path_value("TRANSCRIPTX_TRANSCRIPTS_DIR") or (
        data_dir / "transcripts"
    )
    # OUTPUTS_DIR: allow tests/CI to override (e.g. tmp_path) before importing app modules
    outputs_dir_val = os.getenv("TRANSCRIPTX_OUTPUT_DIR")
    outputs_dir = (
        Path(outputs_dir_val).expanduser()
        if outputs_dir_val
        else (data_dir / "outputs")
    )
    profiles_dir = _env_path_value("TRANSCRIPTX_PROFILES_DIR") or (
        config_dir / "profiles"
    )
    state_dir = data_dir / "state"
    wav_backup_env = _env_path_value("TRANSCRIPTX_WAV_BACKUP_DIR")
    wav_storage_legacy = _env_path_value("TRANSCRIPTX_WAV_STORAGE_DIR")
    if wav_storage_legacy and not wav_backup_env:
        _log.warning(
            "TRANSCRIPTX_WAV_STORAGE_DIR is deprecated; use TRANSCRIPTX_WAV_BACKUP_DIR instead"
        )
    wav_backup_dir = (
        wav_backup_env or wav_storage_legacy or (data_dir / "backups" / "wav")
    )
    return PathSettings(
        project_root=project_root,
        data_dir=data_dir,
        config_dir=config_dir,
        profiles_dir=profiles_dir,
        recordings_dir=recordings_dir,
        transcripts_dir=transcripts_dir,
        readable_transcripts_dir=transcripts_dir / "readable",
        outputs_dir=outputs_dir,
        group_outputs_dir=outputs_dir / "groups",
        preprocessing_dir=data_dir / "preprocessing",
        state_dir=state_dir,
        processing_state_file=state_dir / "processing_state.json",
        wav_backup_dir=wav_backup_dir,
        state_backup_dir=data_dir / "backups" / "processing_state",
        audio_playback_cache_dir=data_dir / "cache" / "audio_playback",
        voice_cache_dir=data_dir / "cache" / "voice",
    )


PATHS = _build_paths()

# Backward-compatible aliases (all Path)
PROJECT_ROOT = PATHS.project_root
DATA_DIR = PATHS.data_dir
CONFIG_DIR = PATHS.config_dir
RECORDINGS_DIR = PATHS.recordings_dir
DIARISED_TRANSCRIPTS_DIR = PATHS.transcripts_dir
READABLE_TRANSCRIPTS_DIR = PATHS.readable_transcripts_dir
OUTPUTS_DIR = PATHS.outputs_dir
GROUP_OUTPUTS_DIR = PATHS.group_outputs_dir
PROFILES_DIR = PATHS.profiles_dir
WAV_STORAGE_DIR = PATHS.wav_backup_dir
PREPROCESSING_DIR = PATHS.preprocessing_dir
AUDIO_PLAYBACK_CACHE_DIR = PATHS.audio_playback_cache_dir
PROCESSING_STATE_FILE = PATHS.processing_state_file
STATE_DIR = PATHS.state_dir
STATE_BACKUP_DIR = PATHS.state_backup_dir

# Deprecated convenience aliases (not in PathSettings)
WAV_OUTPUT_DIR = PATHS.recordings_dir
PERFORMANCE_LOGS_DIR = PATHS.data_dir


def _migrate_state_paths() -> None:
    """One-time migration: transcriptx_data/ -> state/, processing_state.json into state/."""
    data_dir = PATHS.data_dir
    state_dir = PATHS.state_dir
    old_db_dir = data_dir / "transcriptx_data"
    old_state_file = data_dir / "processing_state.json"
    new_state_file = PATHS.processing_state_file

    # Migrate transcriptx_data/ -> state/
    if old_db_dir.exists() and not state_dir.exists():
        try:
            old_db_dir.rename(state_dir)
            _log.info("Migrated %s to %s", old_db_dir, state_dir)
        except (PermissionError, OSError) as e:
            _log.warning("Could not migrate %s to %s: %s", old_db_dir, state_dir, e)
    elif old_db_dir.exists() and state_dir.exists():
        _log.warning(
            "Both %s and %s exist; skipping migration. Remove one manually if needed.",
            old_db_dir,
            state_dir,
        )

    # Migrate processing_state.json from data_dir to state_dir
    if old_state_file.exists() and not new_state_file.exists():
        try:
            state_dir.mkdir(parents=True, exist_ok=True)
            import shutil

            shutil.move(str(old_state_file), str(new_state_file))
            _log.info("Migrated %s to %s", old_state_file, new_state_file)
        except (PermissionError, OSError) as e:
            _log.warning(
                "Could not migrate %s to %s: %s", old_state_file, new_state_file, e
            )
    elif old_state_file.exists() and new_state_file.exists():
        _log.warning(
            "Both %s and %s exist; skipping migration. Remove one manually if needed.",
            old_state_file,
            new_state_file,
        )


def ensure_data_dirs() -> None:
    """Create core data directories if they do not exist.

    On permission errors (e.g. read-only DATA_DIR in Docker web container),
    logs a warning and continues so read-only modes (e.g. web-viewer) can start.
    """
    _migrate_state_paths()
    dirs = [
        PATHS.recordings_dir,
        PATHS.transcripts_dir,
        PATHS.outputs_dir,
        PATHS.group_outputs_dir,
        PATHS.wav_backup_dir,
        PATHS.state_backup_dir,
        PATHS.preprocessing_dir,
        PATHS.audio_playback_cache_dir,
        PATHS.voice_cache_dir,
        PATHS.profiles_dir,
        PATHS.state_dir,
        PATHS.data_dir / "speaker_profiles",
    ]
    for d in dirs:
        try:
            d.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError) as e:
            _log.warning(
                "Could not create data directory %s: %s (continuing; some features may be unavailable)",
                d,
                e,
            )
