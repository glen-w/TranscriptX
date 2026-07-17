"""Dir-fsync errno mapping: UNSUPPORTED vs FAILED (no string matching)."""

from __future__ import annotations

import errno
from pathlib import Path
from unittest.mock import patch

import pytest

from transcriptx.web.services.run_cleanup.journal import DirFsyncOutcome, fsync_dir


@pytest.mark.unit
def test_fsync_dir_ok(tmp_path: Path) -> None:
    result = fsync_dir(tmp_path)
    assert result.outcome is DirFsyncOutcome.OK


@pytest.mark.unit
@pytest.mark.parametrize(
    "err",
    [errno.EINVAL, errno.ENOTSUP, errno.EBADF],
)
def test_fsync_dir_unsupported_errnos(tmp_path: Path, err: int) -> None:
    real_open = __import__("os").open

    def boom(path, flags, *args):
        if Path(path) == tmp_path:
            raise OSError(err, "injected")
        return real_open(path, flags, *args)

    with patch("os.open", side_effect=boom):
        result = fsync_dir(tmp_path)
    assert result.outcome is DirFsyncOutcome.UNSUPPORTED


@pytest.mark.unit
def test_fsync_dir_genuine_failure(tmp_path: Path) -> None:
    real_open = __import__("os").open

    def boom(path, flags, *args):
        if Path(path) == tmp_path:
            raise OSError(errno.EIO, "injected i/o")
        return real_open(path, flags, *args)

    with patch("os.open", side_effect=boom):
        result = fsync_dir(tmp_path)
    assert result.outcome is DirFsyncOutcome.FAILED
