"""Shared filename policy and RenameNames / RenamePaths constructors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from transcriptx.core.utils._path_core import (
    get_canonical_base_name,
    get_transcript_dir,
)

KNOWN_EXTENSIONS = frozenset(
    {".json", ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac", ".wma"}
)

# Separators recognised when matching anchored artifact basenames.
ARTIFACT_SEPARATORS = frozenset({"_", "-", ".", " "})

_CONTROL_OR_NUL = re.compile(r"[\x00-\x1f\x7f]")


def normalize_base_name(raw_name: str) -> str:
    """Strip recognised extensions and outer whitespace/trailing dots from a user name."""
    name = (raw_name or "").strip().rstrip(".")
    suffix = Path(name).suffix.lower()
    if suffix in KNOWN_EXTENSIONS:
        name = name[: -len(suffix)]
    return name.strip()


def validate_target_name(
    current_base_name: str,
    raw_target_name: str,
    *,
    transcript_parent: Path | None = None,
) -> tuple[bool, str]:
    """Validate a user-facing rename target (post-normalization checks).

    Rejects empty names, ``.`` / ``..``, path separators, NUL/control characters,
    trailing spaces/dots, and any name that would escape or change the transcript
    parent directory.
    """
    target = normalize_base_name(raw_target_name)
    if not target:
        return False, "Please provide a new file name."
    if target in {".", ".."}:
        return False, "File name cannot be '.' or '..'."
    if "/" in target or "\\" in target or ":" in target:
        return False, "File name must not contain path separators."
    if any(ch in target for ch in '*?"<>|'):
        return False, 'File name contains invalid characters: *, ?, ", <, >, |'
    if _CONTROL_OR_NUL.search(target):
        return False, "File name contains control characters."
    if target != target.rstrip(" ."):
        return False, "File name must not end with spaces or dots."
    if target == normalize_base_name(current_base_name):
        return False, "New file name must be different from the current name."
    if transcript_parent is not None:
        candidate = (transcript_parent / f"{target}.json").resolve()
        try:
            if candidate.parent.resolve() != Path(transcript_parent).resolve():
                return False, "File name would escape the transcript parent directory."
        except OSError:
            return False, "Could not resolve target transcript path."
    return True, ""


def paths_are_case_only_rename(source: Path, dest: Path) -> bool:
    """True when source and dest differ only by case (same parent, case-folded equal)."""
    if source.parent.resolve() != dest.parent.resolve():
        return False
    if source.name == dest.name:
        return False
    return source.name.casefold() == dest.name.casefold()


def unique_temp_name(
    directory: Path, final_name: str, *, tag: str = "rename_tmp"
) -> Path:
    """Return a unique temporary path in ``directory`` for an intermediate rename."""
    directory = Path(directory)
    stem = Path(final_name).stem
    suffix = Path(final_name).suffix
    for i in range(10_000):
        candidate = directory / f".{tag}_{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not allocate temporary name in {directory}")


@dataclass(frozen=True)
class RenameNames:
    """Stem and canonical bases derived solely from complete transcript paths."""

    old_stem: str
    new_stem: str
    old_canonical: str
    new_canonical: str

    @classmethod
    def from_paths(cls, old_transcript: Path, new_transcript: Path) -> RenameNames:
        old_transcript = Path(old_transcript)
        new_transcript = Path(new_transcript)
        return cls(
            old_stem=old_transcript.stem,
            new_stem=new_transcript.stem,
            old_canonical=get_canonical_base_name(str(old_transcript)),
            new_canonical=get_canonical_base_name(str(new_transcript)),
        )


@dataclass(frozen=True)
class RenamePaths:
    """Immutable path bundle so callers cannot recompute targets inconsistently."""

    old_transcript: Path
    new_transcript: Path
    old_output_dir: Path
    new_output_dir: Path

    @classmethod
    def from_transcripts(
        cls, old_transcript: Path, new_transcript: Path
    ) -> RenamePaths:
        old_transcript = Path(old_transcript)
        new_transcript = Path(new_transcript)
        return cls(
            old_transcript=old_transcript,
            new_transcript=new_transcript,
            old_output_dir=Path(get_transcript_dir(str(old_transcript))),
            new_output_dir=Path(get_transcript_dir(str(new_transcript))),
        )
