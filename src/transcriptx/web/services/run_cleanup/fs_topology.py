"""Filesystem topology rules for per-descendant device checks.

Cleanup refuses to walk across a device change, so a mount inside a run tree
is never followed or deleted. On overlayfs whose layers sit on different
filesystems, though, directories report the overlay's ``st_dev`` while regular
files report the ``st_dev`` of the layer that holds them. A strict "every
descendant is on ``root_dev``" rule then rejects every run tree on such a host
(common in cloud and container sandboxes).

``DevicePolicy`` keeps the strict rule everywhere except that one case:

* an entry on ``root_dev`` is always fine;
* a directory on another device is a mount: rejected;
* a non-directory on another device is tolerated only when the run root is on
  an overlay mount *and* the entry is not itself a mount point (a bind-mounted
  file is still rejected).

Mount data comes from ``/proc/self/mountinfo`` (Linux only). It is read lazily
on the first mismatch, so hosts where devices always agree pay nothing. With no
mount data the strict rule applies.
"""

from __future__ import annotations

import os
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

MOUNTINFO_PATH = "/proc/self/mountinfo"


@dataclass(frozen=True)
class MountEntry:
    mount_point: str
    fstype: str


def _unescape(field: str) -> str:
    # mountinfo octal-escapes space, tab, newline and backslash.
    return (
        field.replace("\\040", " ")
        .replace("\\011", "\t")
        .replace("\\012", "\n")
        .replace("\\134", "\\")
    )


def parse_mountinfo(text: str) -> tuple[MountEntry, ...]:
    """Parse ``/proc/self/mountinfo`` lines into (mount point, fstype) pairs."""
    mounts: list[MountEntry] = []
    for line in text.splitlines():
        left, sep, right = line.partition(" - ")
        if not sep:
            continue
        fields = left.split()
        tail = right.split()
        if len(fields) < 5 or not tail:
            continue
        mounts.append(MountEntry(mount_point=_unescape(fields[4]), fstype=tail[0]))
    return tuple(mounts)


def read_mounts() -> tuple[MountEntry, ...]:
    if not sys.platform.startswith("linux"):
        return ()
    try:
        return parse_mountinfo(Path(MOUNTINFO_PATH).read_text(encoding="utf-8"))
    except OSError:
        return ()


def _containing_mount(path: str, mounts: tuple[MountEntry, ...]) -> MountEntry | None:
    best: MountEntry | None = None
    for mount in mounts:
        mp = mount.mount_point
        if path == mp or mp == "/" or path.startswith(mp.rstrip("/") + "/"):
            # Longest prefix wins; on ties the later (stacked-on-top) mount wins.
            if best is None or len(mp) >= len(best.mount_point):
                best = mount
    return best


class DevicePolicy:
    """Decide whether a descendant's ``st_dev`` is acceptable under a root."""

    def __init__(self, root: Path | str, root_dev: int) -> None:
        self.root = Path(root)
        self.root_dev = int(root_dev)
        self._loaded = False
        self._overlay_root = False
        self._mount_points: frozenset[str] = frozenset()

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        mounts = read_mounts()
        if not mounts:
            return
        root_real = os.path.realpath(self.root)
        containing = _containing_mount(root_real, mounts)
        self._overlay_root = containing is not None and containing.fstype == "overlay"
        self._mount_points = frozenset(m.mount_point for m in mounts)

    def entry_ok(self, path: Path | str, st: os.stat_result) -> bool:
        if int(st.st_dev) == self.root_dev:
            return True
        if stat.S_ISDIR(st.st_mode):
            return False
        self._load()
        if not self._overlay_root:
            return False
        return os.path.realpath(path) not in self._mount_points
