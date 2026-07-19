"""Archive uploaded originals under transcripts/originals/ with safe disambiguation."""

from __future__ import annotations

import errno
import os
from pathlib import Path


def disambiguate_originals_archive_path(
    original_basename: str,
    originals_dir: Path,
    *,
    staging_path: Path | None = None,
) -> Path:
    """
    Pick a path under ``originals_dir`` for ``original_basename`` without clobbering.

    If ``staging_path`` resolves to the same path as the first candidate, that candidate
    is returned. This avoids treating the file we *just* staged into ``originals/`` as
    a pre-existing duplicate (which would incorrectly produce ``name (1)``).

    Note: existence checks alone are racy. Prefer :func:`exclusive_create_originals_archive`
    when writing new archive bytes.
    """
    originals_dir.mkdir(parents=True, exist_ok=True)
    base = Path(original_basename).name or "uploaded"
    candidate = originals_dir / base
    if not candidate.exists():
        return candidate
    if staging_path is not None:
        try:
            if candidate.resolve() == Path(staging_path).resolve():
                return candidate
        except OSError:
            pass
    stem = Path(base).stem
    suffix = Path(base).suffix
    counter = 1
    while True:
        candidate = originals_dir / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def exclusive_create_originals_archive(
    original_basename: str,
    originals_dir: Path,
    content: bytes,
    *,
    staging_path: Path | None = None,
    max_attempts: int = 10_000,
) -> Path:
    """Create an originals archive with O_CREAT|O_EXCL semantics; return the path.

    Retries with numeric disambiguation when exclusive create races another writer.
    If ``staging_path`` already is the first candidate path, reuse it without rewrite.
    """
    originals_dir.mkdir(parents=True, exist_ok=True)
    base = Path(original_basename).name or "uploaded"
    stem = Path(base).stem
    suffix = Path(base).suffix

    candidates: list[Path] = [originals_dir / base]
    for counter in range(1, max_attempts):
        candidates.append(originals_dir / f"{stem} ({counter}){suffix}")

    for candidate in candidates:
        if staging_path is not None:
            try:
                if candidate.resolve() == Path(staging_path).resolve():
                    return candidate
            except OSError:
                pass
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        try:
            fd = os.open(str(candidate), flags, 0o644)
        except FileExistsError:
            continue
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                continue
            raise
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return candidate

    raise RuntimeError(
        f"Could not exclusively create originals archive for {original_basename!r}"
    )
