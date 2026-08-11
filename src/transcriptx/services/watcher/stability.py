"""Debounce + size/mtime stability gate for watched files."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileIdentity:
    path: str
    st_dev: int
    st_ino: int
    size: int
    mtime_ns: int

    @staticmethod
    def from_lstat(path: Path) -> FileIdentity | None:
        try:
            st = os.lstat(path)
        except OSError:
            return None
        if not hasattr(st, "st_mode"):
            return None
        import stat as stat_mod

        if stat_mod.S_ISLNK(st.st_mode) or not stat_mod.S_ISREG(st.st_mode):
            return None
        mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))
        return FileIdentity(
            path=str(path),
            st_dev=int(st.st_dev),
            st_ino=int(st.st_ino),
            size=int(st.st_size),
            mtime_ns=int(mtime_ns),
        )

    def matches_current(self) -> bool:
        current = FileIdentity.from_lstat(Path(self.path))
        if current is None:
            return False
        return (
            current.st_dev == self.st_dev
            and current.st_ino == self.st_ino
            and current.size == self.size
            and current.mtime_ns == self.mtime_ns
        )


def wait_until_stable(
    path: Path | str,
    *,
    checks: int = 3,
    interval_ms: int = 500,
    timeout_ms: int = 120_000,
) -> FileIdentity | None:
    """Return identity once size/mtime are unchanged for ``checks`` samples.

    Returns None if the file disappears, is not a regular file, or times out.
    """
    target = Path(path)
    interval_s = max(interval_ms, 1) / 1000.0
    deadline = time.monotonic() + max(timeout_ms, interval_ms) / 1000.0
    stable_count = 0
    previous: FileIdentity | None = None

    while time.monotonic() < deadline:
        current = FileIdentity.from_lstat(target)
        if current is None:
            return None
        if (
            previous is not None
            and current.st_dev == previous.st_dev
            and current.st_ino == previous.st_ino
            and current.size == previous.size
            and current.mtime_ns == previous.mtime_ns
        ):
            stable_count += 1
            if stable_count >= max(checks, 1):
                return current
        else:
            stable_count = 1
            previous = current
        time.sleep(interval_s)

    # Final sample after timeout — only accept if already stable enough.
    if previous is not None and stable_count >= max(checks, 1):
        return previous if previous.matches_current() else None
    return None
