"""Enumerate recordings and managed transcripts for duplicate detection."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Sequence

from transcriptx.app.duplicate_cleanup.models import FileFingerprint
from transcriptx.core.audio.types import SUPPORTED_AUDIO_EXTENSIONS
from transcriptx.core.utils.paths import PATHS
from transcriptx.io.transcript_schema import compute_file_hash


def resolve_path(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except OSError:
        return path


def is_under(path: Path, root: Path | None) -> bool:
    if root is None:
        return False
    try:
        resolve_path(path).relative_to(resolve_path(root))
        return True
    except (ValueError, OSError):
        return False


def list_audio_files(
    recordings_dir: Path | None = None,
    *,
    imports_dir: Path | None = None,
) -> list[Path]:
    """Audio under recordings_dir, excluding the imports/ staging tree."""
    root = Path(recordings_dir) if recordings_dir is not None else PATHS.recordings_dir
    skip = Path(imports_dir) if imports_dir is not None else PATHS.recordings_imports_dir
    if not root.is_dir():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            continue
        if is_under(path, skip):
            continue
        files.append(path)
    return sorted(files, key=lambda item: str(resolve_path(item)))


def list_transcript_files(
    *,
    paths: Sequence[Path] | None = None,
    discover: Callable[[], Sequence[Path]] | None = None,
) -> list[Path]:
    if paths is not None:
        return [Path(item) for item in paths if Path(item).is_file()]
    if discover is not None:
        return [Path(item) for item in discover() if Path(item).is_file()]
    from transcriptx.core.utils.file_discovery import discover_managed_transcript_paths

    return list(discover_managed_transcript_paths())


def fingerprint_file(path: Path) -> FileFingerprint | None:
    """Return size/mtime/sha256, or None if the path cannot be read."""
    try:
        stats = path.stat()
    except OSError:
        return None
    try:
        digest = compute_file_hash(path)
    except OSError:
        return None
    return FileFingerprint(
        path=path,
        size=int(stats.st_size),
        mtime_ns=int(getattr(stats, "st_mtime_ns", int(stats.st_mtime * 1e9))),
        sha256=digest,
    )
