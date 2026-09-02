"""Symlink and containment policy for speaker_profiles trees."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.speaker_profiles.errors import SpeakerProfilePathError
from transcriptx.core.utils import path_safety as _core


def resolve_real(path: Path) -> Path:
    """Expanduser + resolve (follows symlinks)."""
    return _core.resolve_real(path)


def assert_not_symlink(path: Path, *, what: str = "path") -> Path:
    """Reject if the given path itself is a symlink (lexically)."""
    return _core.assert_not_symlink(
        path, what=what, error_cls=SpeakerProfilePathError
    )


def assert_safe_relpath(relpath: str, *, what: str = "relpath") -> str:
    """Reject absolute paths and traversal before any stat/read/staging/backup.

    Voice and operation plan paths must be relative POSIX-style segments under
    the speaker_profiles root. Call this before joining onto the root.
    """
    return _core.assert_safe_relpath(
        relpath, what=what, error_cls=SpeakerProfilePathError
    )


def assert_path_under_root(path: Path, root: Path, *, what: str = "path") -> Path:
    """Resolve path and require it stays under root (blocks symlink escape)."""
    return _core.assert_path_under_root(
        path, root, what=what, error_cls=SpeakerProfilePathError
    )


def assert_speaker_profiles_root(root: Path) -> Path:
    """Reject symlinked speaker_profiles root; return resolved real path."""
    root_path = Path(root)
    if root_path.exists() and root_path.is_symlink():
        raise SpeakerProfilePathError(
            f"symlink rejected for speaker_profiles root: {root_path}"
        )
    return resolve_real(root_path)


def assert_operation_path_under_root(
    path: Path, root: Path, *, what: str = "operation path"
) -> Path:
    """Containment check for operation/staging/backup/file paths."""
    assert_speaker_profiles_root(root)
    return assert_path_under_root(path, root, what=what)


def assert_relpath_under_root(
    relpath: str, root: Path, *, what: str = "relpath"
) -> Path:
    """Lexical relpath safety then join + containment under root."""
    safe = assert_safe_relpath(relpath, what=what)
    return assert_operation_path_under_root(root / safe, root, what=what)
