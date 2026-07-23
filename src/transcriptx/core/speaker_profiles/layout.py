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


def profile_path(profile_id: str, *, root: Path | None = None) -> Path:
    base = root or speaker_profiles_dir()
    path = profiles_dir(base) / f"{profile_id}{PROFILE_FILE_SUFFIX}"
    return assert_operation_path_under_root(path, base, what="profile path")


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
