"""Hardened physical deletion requiring an unforgeable VerifiedStagedTree proof.

The recursive delete implementation is module-private. Callers mint a proof via
``verify_staged_tree`` and pass it to ``safe_rmtree_verified``.
"""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcriptx.web.services.run_cleanup import fd_ops
from transcriptx.web.services.run_cleanup.fingerprint import (
    TreeFingerprintError,
    compute_tree_fingerprint,
)
from transcriptx.web.services.run_cleanup.models import STAGING_DIR_NAME


class PhysicalDeleteUnsafeError(RuntimeError):
    """Raised when deletion cannot be proven safe (no weak fallback)."""


class PhysicalDeletePartialError(PhysicalDeleteUnsafeError):
    """Deletion began but could not complete; staged remnants remain."""

    def __init__(self, message: str, *, mutation_started: bool = True) -> None:
        super().__init__(message)
        self.mutation_started = mutation_started


_PROOF_TOKEN = object()


def platform_supports_nofollow_delete() -> bool:
    return fd_ops.platform_supports_secure_cleanup()


@dataclass(frozen=True)
class VerifiedStagedTree:
    """Proof minted only by verify_staged_tree (private token)."""

    staging_path: str
    staged_dev: int
    staged_ino: int
    planned_filesystem_dev: int
    content_tree_fingerprint: str
    operation_id: str
    canonical_source_path: str
    subject_type: str
    subject_id: str
    run_id: str
    _token: Any = None

    def __post_init__(self) -> None:
        if self._token is not _PROOF_TOKEN:
            raise PhysicalDeleteUnsafeError(
                "VerifiedStagedTree cannot be forged; use verify_staged_tree"
            )

    def matches_path(self, path: Path | str) -> bool:
        return Path(path) == Path(self.staging_path)


def _is_under_cleanup_staging(path: Path) -> bool:
    return STAGING_DIR_NAME in Path(path).parts


def revalidate_staging_path(path: Path) -> Path:
    """Ensure path is under ``.cleanup_staging`` and is not itself a symlink."""
    p = Path(path)
    if not _is_under_cleanup_staging(p):
        raise PhysicalDeleteUnsafeError(
            f"refusing delete outside {STAGING_DIR_NAME}: {p}"
        )
    try:
        st = fd_ops.lstat_nofollow(p)
    except fd_ops.FdOpsUnsupportedError as exc:
        raise PhysicalDeleteUnsafeError(str(exc)) from exc
    except OSError as exc:
        raise PhysicalDeleteUnsafeError(
            f"cannot lstat staging path {p}: {exc}"
        ) from exc
    if stat.S_ISLNK(st.st_mode):
        raise PhysicalDeleteUnsafeError(f"refusing delete of symlink staging path: {p}")
    if not stat.S_ISDIR(st.st_mode):
        raise PhysicalDeleteUnsafeError(f"staging path is not a directory: {p}")
    return p


def verify_staged_tree(
    *,
    staging_path: Path,
    planned_filesystem_dev: int,
    planned_filesystem_ino: int,
    planned_fingerprint: str | None,
    staged_dev: int | None,
    staged_ino: int | None,
    operation_id: str,
    canonical_source_path: str,
    subject_type: str = "",
    subject_id: str = "",
    run_id: str = "",
    source_must_be_absent: bool = True,
    require_fingerprint: bool = True,
) -> VerifiedStagedTree:
    """Verify staged tree identity (+ fingerprint unless partial-retry)."""
    p = revalidate_staging_path(Path(staging_path))
    try:
        st = fd_ops.lstat_nofollow(p)
    except OSError as exc:
        raise PhysicalDeleteUnsafeError(f"cannot lstat staged root: {exc}") from exc

    if stat.S_ISLNK(st.st_mode):
        raise PhysicalDeleteUnsafeError("staged root is a symlink")
    if not stat.S_ISDIR(st.st_mode):
        raise PhysicalDeleteUnsafeError("staged root is not a directory")

    expected_dev = staged_dev if staged_dev is not None else planned_filesystem_dev
    expected_ino = staged_ino if staged_ino is not None else planned_filesystem_ino
    if int(st.st_dev) != int(expected_dev) or int(st.st_ino) != int(expected_ino):
        raise PhysicalDeleteUnsafeError(
            f"staged identity mismatch: got dev={st.st_dev} ino={st.st_ino}, "
            f"expected dev={expected_dev} ino={expected_ino}"
        )
    if int(st.st_dev) != int(planned_filesystem_dev):
        raise PhysicalDeleteUnsafeError(
            f"staged device {st.st_dev} != planned {planned_filesystem_dev}"
        )

    fingerprint = planned_fingerprint or ""
    if require_fingerprint:
        if not planned_fingerprint:
            raise PhysicalDeleteUnsafeError("planned fingerprint required")
        try:
            fp, _, _ = compute_tree_fingerprint(p, planned_filesystem_dev)
        except TreeFingerprintError as exc:
            raise PhysicalDeleteUnsafeError(
                f"staged fingerprint failed: {exc}"
            ) from exc
        if fp != planned_fingerprint:
            raise PhysicalDeleteUnsafeError("staged content fingerprint mismatch")
        fingerprint = fp

    if source_must_be_absent:
        src = Path(canonical_source_path)
        if fd_ops.lexists(src):
            try:
                src_st = fd_ops.lstat_nofollow(src)
                if int(src_st.st_ino) == int(planned_filesystem_ino) and int(
                    src_st.st_dev
                ) == int(planned_filesystem_dev):
                    raise PhysicalDeleteUnsafeError(
                        "source path still present with original identity"
                    )
            except OSError:
                pass

    return VerifiedStagedTree(
        staging_path=str(p),
        staged_dev=int(st.st_dev),
        staged_ino=int(st.st_ino),
        planned_filesystem_dev=int(planned_filesystem_dev),
        content_tree_fingerprint=fingerprint,
        operation_id=operation_id,
        canonical_source_path=canonical_source_path,
        subject_type=subject_type,
        subject_id=subject_id,
        run_id=run_id,
        _token=_PROOF_TOKEN,
    )


def _rmtree_nofollow_fd(
    topfd: int,
    path_for_errors: Path,
    expected_dev: int,
    *,
    mutation_started: list[bool],
) -> None:
    """Descriptor-relative recursive delete: scan then delete; refuse symlinks."""
    try:
        with os.scandir(topfd) as it:
            entries = list(it)
    except OSError as exc:
        err = PhysicalDeleteUnsafeError(
            f"cannot scandir staging tree {path_for_errors}: {exc}"
        )
        if mutation_started[0]:
            raise PhysicalDeletePartialError(str(err)) from exc
        raise err from exc

    validated: list[tuple[str, bool]] = []
    for entry in entries:
        if entry.is_symlink():
            err = PhysicalDeleteUnsafeError(
                f"refusing descendant symlink: {path_for_errors / entry.name}"
            )
            if mutation_started[0]:
                raise PhysicalDeletePartialError(str(err))
            raise err
        st = entry.stat(follow_symlinks=False)
        if int(st.st_dev) != int(expected_dev):
            err = PhysicalDeleteUnsafeError(f"device change during scan: {entry.name}")
            if mutation_started[0]:
                raise PhysicalDeletePartialError(str(err))
            raise err
        validated.append((entry.name, entry.is_dir(follow_symlinks=False)))

    for name, is_dir in validated:
        try:
            if is_dir:
                dirfd = fd_ops.open_dir_nofollow(name, dir_fd=topfd)
                try:
                    _rmtree_nofollow_fd(
                        dirfd,
                        path_for_errors / name,
                        expected_dev,
                        mutation_started=mutation_started,
                    )
                finally:
                    fd_ops.close_quiet(dirfd)
                fd_ops.rmdir_nofollow(name, dir_fd=topfd)
                mutation_started[0] = True
            else:
                st = fd_ops.lstat_nofollow(name, dir_fd=topfd)
                if stat.S_ISLNK(st.st_mode):
                    raise PhysicalDeletePartialError(
                        f"symlink appeared during delete: {path_for_errors / name}"
                    )
                if int(st.st_dev) != int(expected_dev):
                    raise PhysicalDeletePartialError(
                        f"device change during delete: {name}"
                    )
                fd_ops.unlink_nofollow(name, dir_fd=topfd)
                mutation_started[0] = True
        except (PhysicalDeletePartialError, PhysicalDeleteUnsafeError):
            raise
        except fd_ops.FdOpsUnsupportedError as exc:
            if mutation_started[0]:
                raise PhysicalDeletePartialError(str(exc)) from exc
            raise PhysicalDeleteUnsafeError(str(exc)) from exc
        except OSError as exc:
            raise PhysicalDeletePartialError(
                f"failed deleting {path_for_errors / name}: {exc}"
            ) from exc


def _fsync_parent(path: Path) -> None:
    """Fsync the parent directory after final rmdir.

    Unsupported platforms are tolerated. Genuine fsync/open failures raise
    ``PhysicalDeletePartialError`` so callers record a retryable partial result
    instead of silent success.
    """
    parent = path.parent
    try:
        fd = fd_ops.open_dir_nofollow(parent)
    except fd_ops.FdOpsUnsupportedError:
        return
    except (AttributeError, NotImplementedError):
        return
    except OSError as exc:
        raise PhysicalDeletePartialError(
            f"cannot open parent for fsync after rmdir: {exc}"
        ) from exc
    try:
        try:
            os.fsync(fd)
        except (AttributeError, NotImplementedError):
            return
        except OSError as exc:
            raise PhysicalDeletePartialError(
                f"parent fsync failed after rmdir: {exc}"
            ) from exc
    finally:
        fd_ops.close_quiet(fd)


def safe_rmtree_verified(proof: VerifiedStagedTree) -> None:
    """Physically delete only a VerifiedStagedTree proof (not a bare path)."""
    from transcriptx.web.services.run_cleanup.faults import fault_point

    if not isinstance(proof, VerifiedStagedTree):
        raise PhysicalDeleteUnsafeError("proof must be VerifiedStagedTree")
    if getattr(proof, "_token", None) is not _PROOF_TOKEN:
        raise PhysicalDeleteUnsafeError("forged VerifiedStagedTree rejected")

    fault_point("during_delete")
    path = Path(proof.staging_path)
    if not proof.matches_path(path):
        raise PhysicalDeleteUnsafeError("proof path mismatch")

    try:
        st = fd_ops.lstat_nofollow(path)
    except OSError as exc:
        raise PhysicalDeleteUnsafeError(f"pre-delete lstat failed: {exc}") from exc
    if int(st.st_dev) != proof.staged_dev or int(st.st_ino) != proof.staged_ino:
        raise PhysicalDeleteUnsafeError("staged identity changed after verification")
    if int(st.st_dev) != int(proof.planned_filesystem_dev):
        raise PhysicalDeleteUnsafeError("planned device mismatch on re-lstat")
    revalidate_staging_path(path)

    if not platform_supports_nofollow_delete():
        raise PhysicalDeleteUnsafeError("platform cannot guarantee no-follow deletion")

    try:
        fd = fd_ops.open_dir_nofollow(path)
    except fd_ops.FdOpsUnsupportedError as exc:
        raise PhysicalDeleteUnsafeError(str(exc)) from exc
    except OSError as exc:
        raise PhysicalDeleteUnsafeError(
            f"cannot open staged root nofollow: {exc}"
        ) from exc
    mutation_started = [False]
    try:
        _rmtree_nofollow_fd(
            fd, path, proof.staged_dev, mutation_started=mutation_started
        )
    finally:
        fd_ops.close_quiet(fd)

    # Final rmdir via parent dir_fd (no path-based rmdir fallback)
    parent = path.parent
    basename = path.name
    try:
        parent_fd = fd_ops.open_dir_nofollow(parent)
    except (OSError, fd_ops.FdOpsUnsupportedError) as exc:
        raise PhysicalDeletePartialError(f"cannot open staging parent: {exc}") from exc
    try:
        try:
            st2 = fd_ops.lstat_nofollow(basename, dir_fd=parent_fd)
        except OSError as exc:
            raise PhysicalDeletePartialError(f"pre-rmdir lstat failed: {exc}") from exc
        if int(st2.st_dev) != proof.staged_dev or int(st2.st_ino) != proof.staged_ino:
            raise PhysicalDeletePartialError(
                "staged root identity changed before rmdir"
            )
        try:
            fd_ops.rmdir_nofollow(basename, dir_fd=parent_fd)
        except fd_ops.FdOpsUnsupportedError as exc:
            raise PhysicalDeletePartialError(str(exc)) from exc
        except OSError as exc:
            raise PhysicalDeletePartialError(f"final rmdir failed: {exc}") from exc
    finally:
        fd_ops.close_quiet(parent_fd)

    _fsync_parent(path)


def safe_rmtree(path: Path) -> None:
    """Legacy entry: refuses bare paths without proof."""
    raise PhysicalDeleteUnsafeError(
        "bare-path safe_rmtree is disabled; use safe_rmtree_verified(VerifiedStagedTree)"
    )
