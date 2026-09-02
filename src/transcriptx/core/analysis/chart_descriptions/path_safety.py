"""Path containment with realpath / symlink awareness."""

from __future__ import annotations

from pathlib import Path

from transcriptx.core.utils.path_safety import resolve_real


def is_path_within_roots(path: Path, allowed_roots: list[Path]) -> bool:
    """Return True if ``path`` realpath is under any allowed root realpath."""
    try:
        target = resolve_real(path)
    except OSError:
        return False
    for root in allowed_roots:
        try:
            root_real = resolve_real(root)
        except OSError:
            continue
        try:
            target.relative_to(root_real)
            return True
        except ValueError:
            continue
    return False


def assert_path_within_roots(path: Path, allowed_roots: list[Path]) -> Path:
    target = resolve_real(path)
    if not is_path_within_roots(target, allowed_roots):
        raise ValueError(f"Path escapes allowed roots: {path}")
    return target
