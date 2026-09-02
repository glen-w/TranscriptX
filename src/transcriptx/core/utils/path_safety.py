"""Lexical relative-path containment helpers shared by stores and writers.

Domain packages wrap these with their own error types. Do not join a
user-supplied name onto a root until ``assert_safe_relpath`` or
``assert_safe_path_segment`` has accepted it.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath


def resolve_real(path: Path, *, strict: bool = False) -> Path:
    """Expanduser + resolve (follows symlinks)."""
    p = Path(path).expanduser()
    if strict:
        return p.resolve()
    return p.resolve(strict=False)


def assert_not_symlink(
    path: Path,
    *,
    what: str = "path",
    error_cls: type[Exception] = ValueError,
) -> Path:
    """Reject if the given path itself is a symlink (lexically)."""
    p = Path(path)
    if p.is_symlink():
        raise error_cls(f"symlink rejected for {what}: {p}")
    return p


def assert_safe_relpath(
    relpath: str,
    *,
    what: str = "relpath",
    error_cls: type[Exception] = ValueError,
) -> str:
    """Reject absolute paths and traversal before any stat/read/staging/backup.

    Returns a POSIX-normalised relative path with no ``.`` or ``..`` segments.
    """
    if not isinstance(relpath, str) or not relpath.strip():
        raise error_cls(f"{what} must be a non-empty relative path")
    raw = relpath.strip()
    if "\x00" in raw:
        raise error_cls(f"{what} must not contain NUL")
    if raw.startswith("/") or raw.startswith("\\"):
        raise error_cls(f"absolute path rejected for {what}: {raw!r}")
    if len(raw) >= 2 and raw[1] == ":":
        raise error_cls(f"absolute path rejected for {what}: {raw!r}")
    if raw.startswith("//") or raw.startswith("\\\\"):
        raise error_cls(f"absolute path rejected for {what}: {raw!r}")
    pure = PurePosixPath(raw.replace("\\", "/"))
    if pure.is_absolute():
        raise error_cls(f"absolute path rejected for {what}: {raw!r}")
    parts = pure.parts
    if not parts or parts == (".",):
        raise error_cls(f"{what} must be a non-empty relative path")
    for part in parts:
        if part in ("", ".", ".."):
            raise error_cls(f"path traversal rejected for {what}: {raw!r}")
    return pure.as_posix()


def assert_safe_path_segment(
    name: str,
    *,
    what: str = "name",
    error_cls: type[Exception] = ValueError,
) -> str:
    """Require a single path segment (no separators, no ``..``)."""
    if not isinstance(name, str) or not name.strip():
        raise error_cls(f"{what} must be a non-empty path segment")
    raw = name.strip()
    if "/" in raw or "\\" in raw:
        raise error_cls(f"path separators rejected for {what}: {raw!r}")
    safe = assert_safe_relpath(raw, what=what, error_cls=error_cls)
    if "/" in safe:
        raise error_cls(f"{what} must be a single path segment: {raw!r}")
    return safe


def assert_path_under_root(
    path: Path,
    root: Path,
    *,
    what: str = "path",
    error_cls: type[Exception] = ValueError,
    reject_symlink_root: bool = True,
) -> Path:
    """Resolve path and require it stays under root (blocks symlink escape)."""
    if reject_symlink_root and Path(root).is_symlink():
        raise error_cls(f"symlink rejected for root: {root}")
    root_resolved = resolve_real(root)
    resolved = resolve_real(path)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise error_cls(
            f"{what} escapes allowed root: {resolved} not under {root_resolved}"
        ) from exc
    return resolved
