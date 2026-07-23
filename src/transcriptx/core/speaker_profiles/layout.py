"""Directory layout helpers for speaker_profiles_dir."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.speaker_profiles.path_safety import (
    assert_operation_path_under_root,
    assert_speaker_profiles_root,
)
from transcriptx.core.speaker_profiles.versioning import (
    EVENT_FILE_SUFFIX,
    LINK_FILE_SUFFIX,
    OPERATION_FILE_SUFFIX,
    PROFILE_FILE_SUFFIX,
    PROJECT_LOCK_NAME,
)
from transcriptx.core.utils.paths import PATHS


def speaker_profiles_dir(data_dir: Path | None = None) -> Path:
    """Canonical speaker_profiles root.

    When ``data_dir`` is omitted, uses ``PATHS.speaker_profiles_dir`` (honours
    ``TRANSCRIPTX_SPEAKER_PROFILES_DIR``, else ``data_dir/speaker_profiles``).
    When ``data_dir`` is passed, always resolves to ``data_dir/speaker_profiles``.
    """
    if data_dir is not None:
        root = Path(data_dir) / "speaker_profiles"
    else:
        root = PATHS.speaker_profiles_dir
    return assert_speaker_profiles_root(root) if root.exists() else root


def speaker_profiles_lock_path(state_dir: Path | None = None) -> Path:
    """Project operation lock path under state_dir."""
    return (state_dir or PATHS.state_dir) / PROJECT_LOCK_NAME


def speaker_profiles_project_lock(state_dir: Path | None = None):
    """Shared re-entrant project lock for Phase 1 + voice mutations.

    Uses a sentinel file beside ``speaker_profiles.lock`` so every caller
    (SpeakerProfileService, VoiceAcceptanceOwner, MatchService, wipe, …)
    serializes on the same flock identity.
    """
    from transcriptx.core.utils.file_lock import FileLock

    lock_path = speaker_profiles_lock_path(state_dir)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    sentinel = lock_path.with_suffix(".lock.target")
    if not sentinel.exists():
        sentinel.write_text("", encoding="utf-8")
    return FileLock(sentinel, timeout=60, blocking=True)


def profiles_dir(root: Path | None = None) -> Path:
    return (root or speaker_profiles_dir()) / "profiles"


def links_dir(root: Path | None = None) -> Path:
    return (root or speaker_profiles_dir()) / "links"


def events_dir(root: Path | None = None) -> Path:
    return (root or speaker_profiles_dir()) / "events"


def operations_dir(root: Path | None = None) -> Path:
    return (root or speaker_profiles_dir()) / "operations"


def cache_dir(root: Path | None = None) -> Path:
    return (root or speaker_profiles_dir()) / ".cache"


def voice_dir(root: Path | None = None) -> Path:
    return (root or speaker_profiles_dir()) / "voice"


def voice_cache_dir(root: Path | None = None) -> Path:
    return cache_dir(root) / "voice"


def privacy_settings_path(root: Path | None = None) -> Path:
    from transcriptx.core.speaker_profiles.voice.versioning import (
        PRIVACY_SETTINGS_FILENAME,
    )

    base = root or speaker_profiles_dir()
    path = voice_dir(base) / PRIVACY_SETTINGS_FILENAME
    return assert_operation_path_under_root(path, base, what="voice privacy path")


def profile_path(profile_id: str, *, root: Path | None = None) -> Path:
    base = root or speaker_profiles_dir()
    path = profiles_dir(base) / f"{profile_id}{PROFILE_FILE_SUFFIX}"
    return assert_operation_path_under_root(path, base, what="profile path")


def avatar_path(profile_id: str, *, root: Path | None = None) -> Path:
    base = root or speaker_profiles_dir()
    path = profiles_dir(base) / "assets" / profile_id / "avatar.webp"
    return assert_operation_path_under_root(path, base, what="avatar path")


def link_path(link_file_key: str, *, root: Path | None = None) -> Path:
    base = root or speaker_profiles_dir()
    path = links_dir(base) / f"{link_file_key}{LINK_FILE_SUFFIX}"
    return assert_operation_path_under_root(path, base, what="link path")


def event_path(idempotency_id: str, *, root: Path | None = None) -> Path:
    base = root or speaker_profiles_dir()
    path = events_dir(base) / f"{idempotency_id}{EVENT_FILE_SUFFIX}"
    return assert_operation_path_under_root(path, base, what="event path")


def operation_path(operation_id: str, *, root: Path | None = None) -> Path:
    base = root or speaker_profiles_dir()
    path = operations_dir(base) / f"{operation_id}{OPERATION_FILE_SUFFIX}"
    return assert_operation_path_under_root(path, base, what="operation path")


def operation_staging_dir(operation_id: str, *, root: Path | None = None) -> Path:
    base = root or speaker_profiles_dir()
    path = operations_dir(base) / operation_id / "staging"
    return assert_operation_path_under_root(path, base, what="staging path")


def operation_backup_dir(operation_id: str, *, root: Path | None = None) -> Path:
    base = root or speaker_profiles_dir()
    path = operations_dir(base) / operation_id / "backup"
    return assert_operation_path_under_root(path, base, what="backup path")


def iter_paths_for_ordinary_backup(root: Path | None = None) -> list[Path]:
    """Durable speaker_profiles files for ordinary backup/export (excludes voice/).

    Callers that walk ``speaker_profiles_dir`` for project archives **must** use
    this helper (or ``iter_speaker_profiles_paths_for_backup``) instead of raw
    ``rglob`` so biometric-derived ``voice/`` and ``.cache/voice/`` stay out.
    """
    from transcriptx.core.speaker_profiles.voice.backup_inventory import (
        iter_speaker_profiles_paths_for_backup,
    )

    return iter_speaker_profiles_paths_for_backup(root or speaker_profiles_dir())
