"""Archive uploaded originals under transcripts/originals/ with safe disambiguation."""

from __future__ import annotations

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
