"""Path and storage roots for TranscriptX. See docs/runtime/STORAGE.md for policy."""

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
    """Where to discover recordings; may be read-only (e.g. Docker :ro mount)."""
    recordings_imports_dir: Path
    """Writable directory for uploaded files (imports). Falls back under DATA_DIR when recordings_dir is read-only.
    Code may delete files only from this directory (e.g. after backup); never delete from recordings_dir root."""
    transcripts_dir: Path
    transcripts_imports_dir: Path
    transcripts_originals_dir: Path
    transcripts_metadata_dir: Path
    transcripts_speaker_maps_dir: Path
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
    wav_backup_dir = wav_backup_env or (data_dir / "backups" / "wav")
    # Writable directory for uploads: env override, else recordings_dir/imports if writable, else data/recordings/imports
    imports_env = _env_path_value("TRANSCRIPTX_IMPORTS_DIR")
    if imports_env is not None:
        recordings_imports_dir = imports_env
    elif recordings_dir.exists() and os.access(str(recordings_dir), os.W_OK):
        recordings_imports_dir = recordings_dir / "imports"
    else:
        recordings_imports_dir = data_dir / "recordings" / "imports"
        if recordings_dir != (data_dir / "recordings"):
            _log.info(
                "RECORDINGS_DIR %s is read-only or missing; uploads will use %s",
                recordings_dir,
                recordings_imports_dir,
            )
    return PathSettings(
        project_root=project_root,
        data_dir=data_dir,
        config_dir=config_dir,
        profiles_dir=profiles_dir,
        recordings_dir=recordings_dir,
        recordings_imports_dir=recordings_imports_dir,
        transcripts_dir=transcripts_dir,
        transcripts_imports_dir=transcripts_dir / "imports",
        transcripts_originals_dir=transcripts_dir / "originals",
        transcripts_metadata_dir=transcripts_dir / "metadata",
        transcripts_speaker_maps_dir=transcripts_dir / "metadata" / "speaker_maps",
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
RECORDINGS_IMPORTS_DIR = PATHS.recordings_imports_dir
DIARISED_TRANSCRIPTS_DIR = PATHS.transcripts_dir
TRANSCRIPTS_IMPORTS_DIR = PATHS.transcripts_imports_dir
TRANSCRIPTS_ORIGINALS_DIR = PATHS.transcripts_originals_dir
TRANSCRIPTS_METADATA_DIR = PATHS.transcripts_metadata_dir
TRANSCRIPTS_SPEAKER_MAPS_DIR = PATHS.transcripts_speaker_maps_dir
READABLE_TRANSCRIPTS_DIR = PATHS.readable_transcripts_dir
OUTPUTS_DIR = PATHS.outputs_dir
GROUP_OUTPUTS_DIR = PATHS.group_outputs_dir
PROFILES_DIR = PATHS.profiles_dir
PREPROCESSING_DIR = PATHS.preprocessing_dir
AUDIO_PLAYBACK_CACHE_DIR = PATHS.audio_playback_cache_dir
PROCESSING_STATE_FILE = PATHS.processing_state_file
STATE_DIR = PATHS.state_dir
STATE_BACKUP_DIR = PATHS.state_backup_dir


def ensure_data_dirs() -> None:
    """Create core data directories if they do not exist.

    On permission errors (e.g. read-only DATA_DIR in Docker web container),
    logs a warning and continues so read-only modes (e.g. web interface) can start.
    """
    dirs = [
        PATHS.recordings_dir,
        PATHS.recordings_imports_dir,
        PATHS.transcripts_dir,
        PATHS.transcripts_imports_dir,
        PATHS.transcripts_originals_dir,
        PATHS.transcripts_metadata_dir,
        PATHS.transcripts_speaker_maps_dir,
        PATHS.transcripts_speaker_maps_dir,
        PATHS.outputs_dir,
        PATHS.group_outputs_dir,
        PATHS.wav_backup_dir,
        PATHS.state_backup_dir,
        PATHS.preprocessing_dir,
        PATHS.audio_playback_cache_dir,
        PATHS.voice_cache_dir,
        PATHS.profiles_dir,
        PATHS.state_dir,
        PATHS.data_dir / "groups",
        PATHS.data_dir / "corrections",
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


def canonical_transcript_relpath(transcript_path: Path) -> Path:
    """Return path of a canonical processed transcript relative to PATHS.transcripts_dir.

    Enforces that:
    - transcript_path is under PATHS.transcripts_dir
    - transcript_path is not under PATHS.transcript_originals_dir
    - transcript_path is not under PATHS.transcripts_metadata_dir

    Raises a ValueError if any of these invariants are violated.
    """
    resolved = Path(transcript_path).expanduser().resolve()
    transcripts_root = PATHS.transcripts_dir.resolve()
    originals_root = PATHS.transcripts_originals_dir.resolve()
    metadata_root = PATHS.transcripts_metadata_dir.resolve()

    try:
        rel = resolved.relative_to(transcripts_root)
    except ValueError as exc:  # not under transcripts_dir
        raise ValueError(
            f"transcript_path {resolved} is outside transcripts_dir {transcripts_root}"
        ) from exc

    if originals_root in resolved.parents:
        raise ValueError(
            f"transcript_path {resolved} is under originals_dir {originals_root}, "
            "which is not a canonical processed transcript location"
        )
    if metadata_root in resolved.parents:
        raise ValueError(
            f"transcript_path {resolved} is under metadata_dir {metadata_root}, "
            "which is reserved for transcript-associated sidecars"
        )
    return rel


def transcript_metadata_path_for(
    transcript_path: Path, *, kind: str, suffix: str
) -> Path:
    """Compute the path for a transcript-associated sidecar under metadata/.

    The sidecar path:
    - mirrors the canonical transcript's path relative to PATHS.transcripts_dir
    - lives under PATHS.transcripts_metadata_dir / kind
    - uses `suffix` as the file extension / suffix
    """
    rel = canonical_transcript_relpath(transcript_path)
    # Replace the final component's suffix while preserving subdirectories
    if rel.suffix:
        base = rel.with_suffix(suffix)
    else:
        base = rel.parent / (rel.name + suffix)
    return PATHS.transcripts_metadata_dir / kind / base


def speaker_map_path_for_transcript(transcript_path: Path) -> Path:
    """Return the path for the speaker map sidecar for a canonical transcript.

    - Uses transcript_metadata_path_for with kind=\"speaker_maps\" and suffix=\".speaker_map.json\"
    - Rejects paths under originals/ or metadata/ via canonical_transcript_relpath
    """
    return transcript_metadata_path_for(
        transcript_path, kind="speaker_maps", suffix=".speaker_map.json"
    )
