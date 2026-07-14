"""Shared staging and zip helpers for artifact and charts export."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence, Union

from transcriptx.export.types import HARD_CAP_BYTES


def assert_under_hard_cap(total_bytes: int, *, hard_cap: int = HARD_CAP_BYTES) -> None:
    """Raise ``ValueError`` when ``total_bytes`` exceeds the export hard cap."""
    if total_bytes > hard_cap:
        raise ValueError("Export exceeds hard cap.")


def copy_items_to_staging(
    staging_dir: Path,
    items: Iterable[tuple[Path, Path]],
) -> None:
    """Copy ``(source_path, export_rel_path)`` pairs into ``staging_dir``."""
    for source_path, export_rel_path in items:
        target = staging_dir / export_rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)


def make_zip_from_staging(staging_dir: Path, zip_path: Path) -> Path:
    """Archive ``staging_dir`` into ``zip_path`` (must end with ``.zip``)."""
    shutil.make_archive(str(zip_path).replace(".zip", ""), "zip", staging_dir)
    return zip_path


def stage_copy_and_zip(
    items: Sequence[tuple[Path, Path]],
    *,
    zip_basename: str,
    write_index: Optional[Callable[[Path], None]] = None,
    return_bytes: bool = False,
    staging_prefix: str = "tx_export_",
    zip_temp_prefix: str = "tx_export_zip_",
) -> Union[Path, bytes]:
    """Stage copies, optionally write an index, then make a zip archive.

    When ``return_bytes`` is True, the zip bytes are returned and temp dirs are
    cleaned up. When False, a persistent temp zip ``Path`` is returned (caller
    owns cleanup of the parent temp directory).
    """
    if return_bytes:
        staging_dir = Path(tempfile.mkdtemp(prefix=staging_prefix))
        zip_temp_dir = Path(tempfile.mkdtemp(prefix=zip_temp_prefix))
        zip_file = zip_temp_dir / f"{zip_basename}.zip"
        try:
            copy_items_to_staging(staging_dir, items)
            if write_index is not None:
                write_index(staging_dir)
            make_zip_from_staging(staging_dir, zip_file)
            return zip_file.read_bytes()
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)
            try:
                zip_file.unlink(missing_ok=True)
            except TypeError:
                if zip_file.exists():
                    zip_file.unlink()
            shutil.rmtree(zip_temp_dir, ignore_errors=True)

    temp_dir = Path(tempfile.mkdtemp(prefix=staging_prefix))
    zip_path = temp_dir / f"{zip_basename}.zip"
    with tempfile.TemporaryDirectory(prefix=f"{staging_prefix}stage_") as staging:
        staging_dir = Path(staging)
        copy_items_to_staging(staging_dir, items)
        if write_index is not None:
            write_index(staging_dir)
        make_zip_from_staging(staging_dir, zip_path)
    return zip_path
