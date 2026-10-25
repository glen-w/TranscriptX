"""Device rules on overlayfs with layers on different filesystems.

There, directories report the overlay's ``st_dev`` while regular files report
the ``st_dev`` of their layer. CI cannot mount overlays, so these tests
simulate it: a wrapped ``os.scandir`` shifts ``st_dev`` for chosen entries and
``fs_topology.read_mounts`` is stubbed.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Callable

import pytest

from transcriptx.web.services.run_cleanup import fd_ops, fs_topology
from transcriptx.web.services.run_cleanup.fingerprint import (
    TreeFingerprintError,
    compute_tree_fingerprint,
)
from transcriptx.web.services.run_cleanup.fs_topology import (
    DevicePolicy,
    MountEntry,
    parse_mountinfo,
)
from transcriptx.web.services.run_cleanup.physical_delete import (
    PhysicalDeleteUnsafeError,
    _rmtree_nofollow_fd,
)

_SHIFT = 7

_real_scandir = os.scandir


def _with_dev(st: os.stat_result, dev: int) -> os.stat_result:
    fields = list(st[:10])
    fields[2] = dev
    # Keep float and ns timestamps (fields 10-15), which the fingerprint reads.
    fields += [st.st_atime, st.st_mtime, st.st_ctime]
    fields += [st.st_atime_ns, st.st_mtime_ns, st.st_ctime_ns]
    return os.stat_result(fields)


class _ShiftedEntry:
    def __init__(self, entry: os.DirEntry, shift: Callable[[os.stat_result], bool]):
        self._entry = entry
        self._shift = shift
        self.name = entry.name
        self.path = entry.path

    def stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
        st = self._entry.stat(follow_symlinks=follow_symlinks)
        if self._shift(st):
            return _with_dev(st, int(st.st_dev) + _SHIFT)
        return st

    def is_dir(self, *, follow_symlinks: bool = True) -> bool:
        return self._entry.is_dir(follow_symlinks=follow_symlinks)

    def is_symlink(self) -> bool:
        return self._entry.is_symlink()


class _ShiftedScandir:
    def __init__(self, path, shift):
        self._it = _real_scandir(path)
        self._shift = shift

    def __enter__(self):
        return [_ShiftedEntry(e, self._shift) for e in self._it]

    def __exit__(self, *exc) -> None:
        self._it.close()


def _shift_files(st: os.stat_result) -> bool:
    return not stat.S_ISDIR(st.st_mode)


def _shift_dirs(st: os.stat_result) -> bool:
    return stat.S_ISDIR(st.st_mode)


@pytest.fixture
def run_tree(tmp_path: Path) -> Path:
    run = tmp_path / "outputs" / "slug" / "run1"
    (run / "charts").mkdir(parents=True)
    (run / "artifact.txt").write_text("a", encoding="utf-8")
    (run / "charts" / "plot.json").write_text("{}", encoding="utf-8")
    return run


def _mounts(monkeypatch, mounts: tuple[MountEntry, ...]) -> None:
    monkeypatch.setattr(fs_topology, "read_mounts", lambda: mounts)


def _overlay_at(path: Path) -> tuple[MountEntry, ...]:
    return (MountEntry("/", "ext4"), MountEntry(os.path.realpath(path), "overlay"))


def _shift(monkeypatch, shift) -> None:
    monkeypatch.setattr(os, "scandir", lambda p: _ShiftedScandir(p, shift))


# --- mountinfo parsing ----------------------------------------------------


def test_parse_mountinfo_reads_mount_point_and_fstype() -> None:
    text = (
        "22 1 0:21 / / rw,relatime - ext4 /dev/vda rw\n"
        "55 22 0:44 / /work/my\\040dir rw,relatime shared:1 - overlay overlay rw\n"
        "garbage line without separator\n"
    )
    assert parse_mountinfo(text) == (
        MountEntry("/", "ext4"),
        MountEntry("/work/my dir", "overlay"),
    )


# --- DevicePolicy ---------------------------------------------------------


def _st(mode: int, dev: int) -> os.stat_result:
    return os.stat_result((mode, 1, dev, 1, 0, 0, 0, 0, 0, 0))


def test_policy_same_device_always_ok(monkeypatch, tmp_path: Path) -> None:
    _mounts(monkeypatch, ())
    policy = DevicePolicy(tmp_path, 10)
    assert policy.entry_ok(tmp_path / "f", _st(stat.S_IFREG, 10))
    assert policy.entry_ok(tmp_path / "d", _st(stat.S_IFDIR, 10))


def test_policy_rejects_file_change_without_mount_data(
    monkeypatch, tmp_path: Path
) -> None:
    _mounts(monkeypatch, ())
    assert not DevicePolicy(tmp_path, 10).entry_ok(
        tmp_path / "f", _st(stat.S_IFREG, 11)
    )


def test_policy_rejects_file_change_on_non_overlay(monkeypatch, tmp_path: Path) -> None:
    _mounts(monkeypatch, (MountEntry("/", "ext4"),))
    assert not DevicePolicy(tmp_path, 10).entry_ok(
        tmp_path / "f", _st(stat.S_IFREG, 11)
    )


def test_policy_tolerates_file_change_on_overlay(monkeypatch, tmp_path: Path) -> None:
    _mounts(monkeypatch, _overlay_at(tmp_path))
    assert DevicePolicy(tmp_path, 10).entry_ok(tmp_path / "f", _st(stat.S_IFREG, 11))


def test_policy_rejects_directory_change_on_overlay(
    monkeypatch, tmp_path: Path
) -> None:
    _mounts(monkeypatch, _overlay_at(tmp_path))
    assert not DevicePolicy(tmp_path, 10).entry_ok(
        tmp_path / "d", _st(stat.S_IFDIR, 11)
    )


def test_policy_rejects_bind_mounted_file_on_overlay(
    monkeypatch, tmp_path: Path
) -> None:
    bound = tmp_path / "bound.txt"
    bound.write_text("x", encoding="utf-8")
    mounts = _overlay_at(tmp_path) + (MountEntry(os.path.realpath(bound), "ext4"),)
    _mounts(monkeypatch, mounts)
    assert not DevicePolicy(tmp_path, 10).entry_ok(bound, _st(stat.S_IFREG, 11))


def test_policy_uses_innermost_mount(monkeypatch, tmp_path: Path) -> None:
    inner = tmp_path / "inner"
    inner.mkdir()
    mounts = _overlay_at(tmp_path) + (MountEntry(os.path.realpath(inner), "ext4"),)
    _mounts(monkeypatch, mounts)
    assert not DevicePolicy(inner, 10).entry_ok(inner / "f", _st(stat.S_IFREG, 11))


# --- fingerprint ----------------------------------------------------------


def test_fingerprint_succeeds_on_overlay_with_file_device_change(
    monkeypatch, run_tree: Path
) -> None:
    root_dev = run_tree.lstat().st_dev
    _mounts(monkeypatch, _overlay_at(run_tree.parents[2]))
    _shift(monkeypatch, _shift_files)
    digest, size, count = compute_tree_fingerprint(run_tree, root_dev)
    assert count == 2 and size == 3
    assert digest == compute_tree_fingerprint(run_tree, root_dev)[0]


def test_fingerprint_rejects_directory_device_change_on_overlay(
    monkeypatch, run_tree: Path
) -> None:
    root_dev = run_tree.lstat().st_dev
    _mounts(monkeypatch, _overlay_at(run_tree.parents[2]))
    _shift(monkeypatch, _shift_dirs)
    with pytest.raises(TreeFingerprintError) as exc:
        compute_tree_fingerprint(run_tree, root_dev)
    assert exc.value.classification == "mount"


def test_fingerprint_rejects_file_device_change_off_overlay(
    monkeypatch, run_tree: Path
) -> None:
    root_dev = run_tree.lstat().st_dev
    _mounts(monkeypatch, (MountEntry("/", "ext4"),))
    _shift(monkeypatch, _shift_files)
    with pytest.raises(TreeFingerprintError) as exc:
        compute_tree_fingerprint(run_tree, root_dev)
    assert exc.value.classification == "mount"


def test_fingerprint_reports_symlink_on_overlay(monkeypatch, run_tree: Path) -> None:
    (run_tree / "link.txt").symlink_to(run_tree / "artifact.txt")
    root_dev = run_tree.lstat().st_dev
    _mounts(monkeypatch, _overlay_at(run_tree.parents[2]))
    _shift(monkeypatch, _shift_files)
    with pytest.raises(TreeFingerprintError) as exc:
        compute_tree_fingerprint(run_tree, root_dev)
    assert exc.value.classification == "symlink"


# --- physical delete walk -------------------------------------------------


def _rmtree(path: Path) -> None:
    fd = fd_ops.open_dir_nofollow(path)
    try:
        _rmtree_nofollow_fd(fd, path, path.lstat().st_dev, mutation_started=[False])
    finally:
        fd_ops.close_quiet(fd)


def test_delete_walk_removes_overlay_tree_with_file_device_change(
    monkeypatch, run_tree: Path
) -> None:
    if not fd_ops.platform_supports_secure_cleanup():
        pytest.skip("platform lacks descriptor-relative delete")
    _mounts(monkeypatch, _overlay_at(run_tree.parents[2]))
    _shift(monkeypatch, _shift_files)
    _rmtree(run_tree)
    assert list(run_tree.iterdir()) == []


def test_delete_walk_refuses_file_device_change_off_overlay(
    monkeypatch, run_tree: Path
) -> None:
    if not fd_ops.platform_supports_secure_cleanup():
        pytest.skip("platform lacks descriptor-relative delete")
    _mounts(monkeypatch, (MountEntry("/", "ext4"),))
    _shift(monkeypatch, _shift_files)
    with pytest.raises(PhysicalDeleteUnsafeError):
        _rmtree(run_tree)
    assert (run_tree / "artifact.txt").exists()
