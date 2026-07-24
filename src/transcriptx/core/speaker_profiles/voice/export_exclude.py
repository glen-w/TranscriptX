"""Exclude voice artefacts from ordinary export / backup discovery."""

from __future__ import annotations

from pathlib import Path


def is_voice_excluded_relpath(relpath: str) -> bool:
    """True when a path under speaker_profiles must not enter ordinary exports."""
    norm = relpath.replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    if norm == "voice" or norm.startswith("voice/"):
        return True
    if norm == ".cache/voice" or norm.startswith(".cache/voice/"):
        return True
    return False


def filter_speaker_profiles_export_paths(root: Path, paths: list[Path]) -> list[Path]:
    """Drop voice subtree and voice cache paths from a candidate export list."""
    root = Path(root).resolve()
    kept: list[Path] = []
    for path in paths:
        try:
            rel = Path(path).resolve().relative_to(root).as_posix()
        except ValueError:
            continue
        if is_voice_excluded_relpath(rel):
            continue
        kept.append(path)
    return kept
