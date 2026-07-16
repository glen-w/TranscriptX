"""Descriptor-anchored secure staging directory creation for cleanup."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from transcriptx.web.services.run_cleanup import fd_ops
from transcriptx.web.services.run_cleanup.models import (
    STAGING_DIR_NAME,
    CleanupTarget,
    RootIdentity,
    SubjectType,
)


class StagingUnsafeError(RuntimeError):
    """Staging directory cannot be created safely on this platform/path."""


class StagingPlatformUnsupportedError(StagingUnsafeError):
    """Required descriptor primitives unavailable — map to top-level BLOCKED."""


def platform_supports_descriptor_staging() -> bool:
    return fd_ops.platform_supports_secure_cleanup()


def collision_proof_staging_basename(
    target: CleanupTarget, *, root_kind: SubjectType | None = None
) -> str:
    """Basename including root kind, subject, run, and TargetIdentity digest."""
    kind = root_kind or target.subject_type
    identity = (
        f"{kind.value}|{target.subject_type.value}|{target.subject_id}|{target.run_id}|"
        f"{target.canonical_path}|{target.filesystem_dev}|{target.filesystem_ino}|"
        f"{target.tree_fingerprint}"
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    sid = target.subject_id.replace("/", "_").replace("\\", "_")
    return (
        f"{kind.value}__{target.subject_type.value}__"
        f"{sid}__{target.run_id}__{digest}"
    )


def intended_staging_path(
    output_root: Path,
    operation_id: str,
    target: CleanupTarget,
) -> Path:
    from transcriptx.web.services.run_cleanup.journal import validate_operation_id

    operation_id = validate_operation_id(operation_id)
    name = collision_proof_staging_basename(target)
    return Path(output_root) / STAGING_DIR_NAME / operation_id / name


@dataclass(frozen=True)
class SecureStagingLayout:
    """Verified staging destination under an exclusive operation directory."""

    output_root: Path
    staging_parent: Path  # .cleanup_staging
    operation_dir: Path
    staging_dest: Path
    basename: str
    root_fd: int | None = None
    staging_fd: int | None = None
    operation_fd: int | None = None

    def close(self) -> None:
        fd_ops.close_quiet(self.operation_fd)
        fd_ops.close_quiet(self.staging_fd)
        fd_ops.close_quiet(self.root_fd)


def _fstat_require_dir_device(
    fd: int, expected_dev: int, *, label: str
) -> os.stat_result:
    st = fd_ops.fstat_fd(fd)
    fd_ops.require_real_dir(st, label=label)
    fd_ops.require_device(st, expected_dev, label=label)
    return st


def ensure_secure_staging_directory(
    output_root: Path,
    operation_id: str,
    target: CleanupTarget,
    planned_root: RootIdentity,
    *,
    allow_existing_operation_dir: bool = False,
) -> SecureStagingLayout:
    """Create staging layout using descriptor-relative ops only.

    Initial execution must pass ``allow_existing_operation_dir=False`` (exclusive).
    Retry may pass True after journal/identity validation.
    """
    from transcriptx.web.services.run_cleanup.journal import validate_operation_id

    if not platform_supports_descriptor_staging():
        raise StagingPlatformUnsupportedError(
            "platform lacks descriptor-relative staging primitives"
        )

    operation_id = validate_operation_id(operation_id)
    if planned_root.dev is None or planned_root.ino is None:
        raise StagingUnsafeError("planned root identity incomplete")
    expected_dev = int(target.filesystem_dev)
    if int(planned_root.dev) != expected_dev:
        raise StagingUnsafeError("target device does not match planned root device")

    root = Path(output_root)
    try:
        root_st = fd_ops.lstat_nofollow(root)
    except fd_ops.FdOpsUnsupportedError as exc:
        raise StagingPlatformUnsupportedError(str(exc)) from exc
    except OSError as exc:
        raise StagingUnsafeError(f"cannot lstat output root: {exc}") from exc
    try:
        fd_ops.require_real_dir(root_st, label="output_root")
    except fd_ops.FdOpsError as exc:
        raise StagingUnsafeError(str(exc)) from exc
    if int(root_st.st_dev) != int(planned_root.dev) or int(root_st.st_ino) != int(
        planned_root.ino
    ):
        raise StagingUnsafeError("output root identity mismatch")

    try:
        root_fd = fd_ops.open_dir_nofollow(root)
    except fd_ops.FdOpsUnsupportedError as exc:
        raise StagingPlatformUnsupportedError(str(exc)) from exc
    try:
        _fstat_require_dir_device(root_fd, int(planned_root.dev), label="output_root")

        staging_name = STAGING_DIR_NAME
        try:
            staging_fd = fd_ops.open_dir_nofollow(staging_name, dir_fd=root_fd)
        except FileNotFoundError:
            try:
                fd_ops.mkdir_nofollow(staging_name, dir_fd=root_fd, mode=0o700)
            except FileExistsError:
                pass
            except fd_ops.FdOpsUnsupportedError as exc:
                raise StagingPlatformUnsupportedError(str(exc)) from exc
            staging_fd = fd_ops.open_dir_nofollow(staging_name, dir_fd=root_fd)
        except fd_ops.FdOpsUnsupportedError as exc:
            raise StagingPlatformUnsupportedError(str(exc)) from exc
        except OSError as exc:
            raise StagingUnsafeError(f"cannot open {STAGING_DIR_NAME}: {exc}") from exc

        try:
            _fstat_require_dir_device(staging_fd, expected_dev, label=STAGING_DIR_NAME)

            try:
                op_fd = fd_ops.open_dir_nofollow(operation_id, dir_fd=staging_fd)
                if not allow_existing_operation_dir:
                    fd_ops.close_quiet(op_fd)
                    raise StagingUnsafeError(
                        f"operation staging directory already exists: {operation_id}"
                    )
            except FileNotFoundError:
                try:
                    fd_ops.mkdir_nofollow(operation_id, dir_fd=staging_fd, mode=0o700)
                except FileExistsError as exc:
                    if not allow_existing_operation_dir:
                        raise StagingUnsafeError(
                            f"operation staging directory already exists: {operation_id}"
                        ) from exc
                except fd_ops.FdOpsUnsupportedError as exc:
                    raise StagingPlatformUnsupportedError(str(exc)) from exc
                op_fd = fd_ops.open_dir_nofollow(operation_id, dir_fd=staging_fd)
            except StagingUnsafeError:
                raise
            except StagingPlatformUnsupportedError:
                raise
            except fd_ops.FdOpsUnsupportedError as exc:
                raise StagingPlatformUnsupportedError(str(exc)) from exc
            except OSError as exc:
                raise StagingUnsafeError(
                    f"cannot create/open operation dir: {exc}"
                ) from exc

            try:
                _fstat_require_dir_device(op_fd, expected_dev, label="operation_dir")
                basename = collision_proof_staging_basename(target)
                try:
                    fd_ops.lstat_nofollow(basename, dir_fd=op_fd)
                    raise StagingUnsafeError(
                        f"staging destination already exists: {basename}"
                    )
                except FileNotFoundError:
                    pass
                except StagingUnsafeError:
                    raise
                except OSError as exc:
                    import errno as errno_mod

                    if getattr(exc, "errno", None) != errno_mod.ENOENT:
                        raise StagingUnsafeError(
                            f"staging destination already exists: {basename}"
                        ) from exc

                staging_parent = root / STAGING_DIR_NAME
                operation_dir = staging_parent / operation_id
                staging_dest = operation_dir / basename
                layout = SecureStagingLayout(
                    output_root=root,
                    staging_parent=staging_parent,
                    operation_dir=operation_dir,
                    staging_dest=staging_dest,
                    basename=basename,
                    root_fd=root_fd,
                    staging_fd=staging_fd,
                    operation_fd=op_fd,
                )
                root_fd = None  # type: ignore[assignment]
                staging_fd = None  # type: ignore[assignment]
                op_fd = None  # type: ignore[assignment]
                return layout
            finally:
                fd_ops.close_quiet(op_fd)
        finally:
            fd_ops.close_quiet(staging_fd)
    finally:
        fd_ops.close_quiet(root_fd)


def revalidate_staging_parent_for_rename(
    layout: SecureStagingLayout, expected_dev: int
) -> None:
    """Re-check operation directory via fstat immediately before rename."""
    if layout.operation_fd is None:
        raise StagingUnsafeError("operation_fd missing")
    _fstat_require_dir_device(
        layout.operation_fd, expected_dev, label="operation_dir_pre_rename"
    )


def rename_into_staging(
    source: Path,
    layout: SecureStagingLayout,
    *,
    expected_dev: int,
    expected_ino: int,
    root_relative_path: str,
) -> None:
    """Rename source into staging via root→subject descriptor-anchored renameat.

    Opens the subject directory from the validated ``layout.root_fd`` and
    re-verifies the run entry relative to that descriptor immediately before
    rename, closing the parent-substitution race of a path-based parent open.
    """
    revalidate_staging_parent_for_rename(layout, expected_dev)
    if layout.operation_fd is None:
        raise StagingUnsafeError("operation_fd missing")
    if layout.root_fd is None:
        raise StagingUnsafeError("root_fd missing")
    parts = Path(root_relative_path).parts
    if len(parts) != 2:
        raise StagingUnsafeError("expected subject/run relative path for rename")
    subject_name, run_name = parts
    # Path is retained only for error context; mutation uses descriptors.
    _ = Path(source)
    try:
        subject_fd = fd_ops.open_dir_nofollow(subject_name, dir_fd=layout.root_fd)
    except fd_ops.FdOpsUnsupportedError as exc:
        raise StagingPlatformUnsupportedError(str(exc)) from exc
    except OSError as exc:
        raise StagingUnsafeError(f"cannot open subject dir for rename: {exc}") from exc
    try:
        try:
            st = fd_ops.lstat_nofollow(run_name, dir_fd=subject_fd)
        except fd_ops.FdOpsUnsupportedError as exc:
            raise StagingPlatformUnsupportedError(str(exc)) from exc
        except OSError as exc:
            raise StagingUnsafeError(f"source lstat failed: {exc}") from exc
        try:
            fd_ops.require_real_dir(st, label="source")
        except fd_ops.FdOpsError as exc:
            raise StagingUnsafeError(str(exc)) from exc
        if int(st.st_dev) != int(expected_dev) or int(st.st_ino) != int(expected_ino):
            raise StagingUnsafeError("source identity changed before rename")
        try:
            fd_ops.renameat(
                run_name,
                layout.basename,
                src_dir_fd=subject_fd,
                dst_dir_fd=layout.operation_fd,
            )
        except fd_ops.FdOpsUnsupportedError as exc:
            raise StagingPlatformUnsupportedError(str(exc)) from exc
    finally:
        fd_ops.close_quiet(subject_fd)
