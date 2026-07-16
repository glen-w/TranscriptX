"""No-follow tree fingerprinting for cleanup targets."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path


class TreeFingerprintError(Exception):
    """Raised when a run tree cannot be safely fingerprinted."""

    def __init__(self, classification: str, reason: str) -> None:
        super().__init__(reason)
        self.classification = classification
        self.reason = reason


def _entry_type_label(mode: int) -> str:
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISDIR(mode):
        return "dir"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "sock"
    if stat.S_ISCHR(mode):
        return "chr"
    if stat.S_ISBLK(mode):
        return "blk"
    return "other"


def compute_tree_fingerprint(run_root: Path, root_dev: int) -> tuple[str, int, int]:
    """Fingerprint *descendant* content of a run tree (scandir + lstat, no follow).

    Root directory identity (dev/ino) is validated separately by callers; this
    fingerprint covers only descendants so it remains stable across a
    same-filesystem rename of the run root itself.

    Returns ``(fingerprint_hex, size_estimate_bytes, file_count)``.

    Raises ``TreeFingerprintError`` if any symlink, mount/device mismatch,
    or unreadable entry is encountered. ``root_dev`` must be the *planned*
    device identity — never substitute a newly observed device.
    """
    root = Path(run_root)
    if not root.exists():
        raise TreeFingerprintError("unreadable", f"run root does not exist: {root}")

    try:
        root_st = root.lstat()
    except OSError as exc:
        raise TreeFingerprintError(
            "unreadable", f"cannot lstat run root {root}: {exc}"
        ) from exc

    if stat.S_ISLNK(root_st.st_mode):
        raise TreeFingerprintError("symlink", f"run root is a symlink: {root}")
    if not stat.S_ISDIR(root_st.st_mode):
        raise TreeFingerprintError("invalid", f"run root is not a directory: {root}")
    if int(root_st.st_dev) != int(root_dev):
        raise TreeFingerprintError(
            "cross_device",
            f"run root device {root_st.st_dev} != expected root_dev {root_dev}",
        )

    lines: list[str] = []
    size_estimate = 0
    file_count = 0
    stack: list[Path] = [root]

    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                names = sorted(entries, key=lambda e: e.name)
                for entry in names:
                    rel = Path(entry.path).relative_to(root).as_posix()
                    try:
                        st = entry.stat(follow_symlinks=False)
                    except OSError as exc:
                        raise TreeFingerprintError(
                            "unreadable",
                            f"cannot lstat {rel}: {exc}",
                        ) from exc

                    mode = st.st_mode
                    if stat.S_ISLNK(mode):
                        raise TreeFingerprintError(
                            "symlink", f"symlink under run tree: {rel}"
                        )
                    if int(st.st_dev) != int(root_dev):
                        raise TreeFingerprintError(
                            "mount",
                            f"device change under run tree: {rel} "
                            f"(dev={st.st_dev} != {root_dev})",
                        )

                    etype = _entry_type_label(mode)
                    mtime_ns = int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1e9)))
                    ctime_ns = int(getattr(st, "st_ctime_ns", int(st.st_ctime * 1e9)))
                    size = int(st.st_size) if stat.S_ISREG(mode) else 0
                    lines.append(
                        f"{rel}|{etype}|{st.st_dev}|{st.st_ino}|{size}|{mtime_ns}|{ctime_ns}"
                    )

                    if stat.S_ISREG(mode):
                        size_estimate += int(st.st_size)
                        file_count += 1
                    elif stat.S_ISDIR(mode):
                        stack.append(Path(entry.path))
        except TreeFingerprintError:
            raise
        except OSError as exc:
            raise TreeFingerprintError(
                "unreadable", f"cannot scandir {current}: {exc}"
            ) from exc

    digest = hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()
    return digest, size_estimate, file_count
