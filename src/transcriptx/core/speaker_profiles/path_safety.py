"""Symlink and containment policy for speaker_profiles trees."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.speaker_profiles.errors import SpeakerProfilePathError


def resolve_real(path: Path) -> Path:
    """Expanduser + resolve (follows symlinks)."""
    return Path(path).expanduser().resolve()


def assert_not_symlink(path: Path, *, what: str = "path") -> Path:
    """Reject if the given path itself is a symlink (lexically)."""
    p = Path(path)
    if p.is_symlink():
        raise SpeakerProfilePathError(f"symlink rejected for {what}: {p}")
    return p


def assert_path_under_root(path: Path, root: Path, *, what: str = "path") -> Path:
    """Resolve path and require it stays under root (blocks symlink escape)."""
    root_resolved = resolve_real(root)
    if root.is_symlink():
        raise SpeakerProfilePathError(f"symlink rejected for root: {root}")
    resolved = resolve_real(path)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise SpeakerProfilePathError(
            f"{what} escapes allowed root: {resolved} not under {root_resolved}"
        ) from exc
    return resolved


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
