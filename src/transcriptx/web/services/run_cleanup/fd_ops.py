"""Shared descriptor-anchored filesystem primitives for cleanup mutation paths.

Staging, under-lock identity walks, retry recovery, and physical deletion must
use only this module. Path-based rename/unlink/rmdir fallbacks are forbidden.
"""

from __future__ import annotations

import errno
import inspect
import os
import stat
from pathlib import Path


class FdOpsUnsupportedError(RuntimeError):
    """Platform lacks required no-follow / dir_fd primitives."""


class FdOpsError(OSError):
    """Descriptor-relative filesystem operation failed."""


def inspect_renameat_support() -> bool:
    """Return False if os.rename cannot accept src_dir_fd/dst_dir_fd."""
    # Prefer the original CPython builtin so test monkeypatches of os.rename
    # do not flip the platform capability gate.
    target = getattr(os, "rename")
    try:
        import builtins  # noqa: F401

        # os.rename is typically a builtin function wrapping renameat
        sig = inspect.signature(target)
    except (TypeError, ValueError):
        return hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY")
    return "src_dir_fd" in sig.parameters and "dst_dir_fd" in sig.parameters


_RENAMEAT_SUPPORTED: bool | None = None


def _renameat_supported_cached() -> bool:
    global _RENAMEAT_SUPPORTED
    if _RENAMEAT_SUPPORTED is None:
        _RENAMEAT_SUPPORTED = inspect_renameat_support()
    return _RENAMEAT_SUPPORTED


def platform_supports_secure_cleanup() -> bool:
    """True when all primitives required for secure cleanup are available."""
    required_attrs = (
        "O_NOFOLLOW",
        "O_DIRECTORY",
        "O_RDONLY",
        "open",
        "mkdir",
        "unlink",
        "rmdir",
        "rename",
        "lstat",
        "fstat",
    )
    if not all(hasattr(os, name) for name in required_attrs):
        return False
    return _renameat_supported_cached()


def _require_supported() -> None:
    if not platform_supports_secure_cleanup():
        raise FdOpsUnsupportedError(
            "platform lacks required staging/deletion descriptor primitives"
        )


def open_dir_nofollow(path: Path | str, *, dir_fd: int | None = None) -> int:
    """Open a directory with O_RDONLY|O_NOFOLLOW|O_DIRECTORY."""
    _require_supported()
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY
    try:
        if dir_fd is None:
            return os.open(str(path), flags)
        return os.open(str(path), flags, dir_fd=dir_fd)
    except TypeError as exc:
        raise FdOpsUnsupportedError(f"dir_fd open unsupported: {exc}") from exc


def open_file_nofollow(
    path: Path | str, *, dir_fd: int | None = None, flags: int = 0
) -> int:
    """Open a file with O_NOFOLLOW (plus caller flags)."""
    _require_supported()
    combined = os.O_RDONLY | os.O_NOFOLLOW | flags
    try:
        if dir_fd is None:
            return os.open(str(path), combined)
        return os.open(str(path), combined, dir_fd=dir_fd)
    except TypeError as exc:
        raise FdOpsUnsupportedError(f"dir_fd file open unsupported: {exc}") from exc


def mkdir_nofollow(name: str, *, dir_fd: int, mode: int = 0o700) -> None:
    """Create a directory relative to an open parent dir_fd."""
    _require_supported()
    try:
        os.mkdir(name, mode=mode, dir_fd=dir_fd)
    except TypeError as exc:
        raise FdOpsUnsupportedError(f"dir_fd mkdir unsupported: {exc}") from exc


def lstat_nofollow(path: Path | str, *, dir_fd: int | None = None) -> os.stat_result:
    """lstat a path, optionally relative to dir_fd (never follows symlinks)."""
    _require_supported()
    try:
        if dir_fd is None:
            return os.lstat(str(path))
        return os.lstat(str(path), dir_fd=dir_fd)
    except TypeError as exc:
        raise FdOpsUnsupportedError(f"dir_fd lstat unsupported: {exc}") from exc


def fstat_fd(fd: int) -> os.stat_result:
    return os.fstat(fd)


def renameat(
    src_name: str,
    dst_name: str,
    *,
    src_dir_fd: int,
    dst_dir_fd: int,
) -> None:
    """Rename relative to verified directory descriptors (no path fallback)."""
    _require_supported()
    try:
        os.rename(src_name, dst_name, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)
    except TypeError as exc:
        raise FdOpsUnsupportedError(
            f"renameat-style os.rename unsupported: {exc}"
        ) from exc


def unlink_nofollow(name: str, *, dir_fd: int) -> None:
    _require_supported()
    try:
        os.unlink(name, dir_fd=dir_fd)
    except TypeError as exc:
        raise FdOpsUnsupportedError(f"dir_fd unlink unsupported: {exc}") from exc


def rmdir_nofollow(name: str, *, dir_fd: int) -> None:
    _require_supported()
    try:
        os.rmdir(name, dir_fd=dir_fd)
    except TypeError as exc:
        raise FdOpsUnsupportedError(f"dir_fd rmdir unsupported: {exc}") from exc


def lexists(path: Path | str) -> bool:
    """True if path exists as a directory entry (including broken symlink)."""
    try:
        os.lstat(str(path))
        return True
    except OSError as exc:
        if exc.errno in {errno.ENOENT, errno.ENOTDIR}:
            return False
        raise


def require_real_dir(st: os.stat_result, *, label: str) -> None:
    if stat.S_ISLNK(st.st_mode):
        raise FdOpsError(f"{label} is a symlink")
    if not stat.S_ISDIR(st.st_mode):
        raise FdOpsError(f"{label} is not a directory")


def require_device(st: os.stat_result, expected_dev: int, *, label: str) -> None:
    if int(st.st_dev) != int(expected_dev):
        raise FdOpsError(f"{label} device {st.st_dev} != expected {expected_dev}")


def close_quiet(fd: int | None) -> None:
    if fd is None:
        return
    try:
        os.close(fd)
    except OSError:
        pass
