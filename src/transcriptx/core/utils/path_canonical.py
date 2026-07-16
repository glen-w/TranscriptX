"""Shared path canonicalisation for lock identity and cleanup."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def canonicalise_path(path: Path | str) -> str:
    """Expand, absolutise, and best-effort resolve a path for identity/lock use.

    Uses resolve(strict=False) when available so missing leaf components still
    normalise parents. Falls back to absolute expanduser on failure. Applies
    platform case normalisation on case-insensitive filesystems (macOS/Windows).
    """
    p = Path(path).expanduser()
    try:
        if not p.is_absolute():
            p = Path.cwd() / p
        try:
            resolved = p.resolve(strict=False)  # type: ignore[call-arg]
        except TypeError:
            resolved = _resolve_existing_parents(p)
        except (OSError, RuntimeError):
            resolved = p.absolute()
    except (OSError, RuntimeError):
        resolved = Path(os.path.abspath(os.path.expanduser(str(path))))

    text = str(resolved)
    if sys.platform == "darwin" or os.name == "nt":
        text = os.path.normcase(text)
    return text


def _resolve_existing_parents(path: Path) -> Path:
    parts = path.parts
    if not parts:
        return path.absolute()
    if path.is_absolute():
        if os.name == "nt":
            current = Path(parts[0] + "\\")
            start = 1
        else:
            current = Path(parts[0] + os.sep)
            start = 1
    else:
        current = Path.cwd()
        start = 0
    remaining: list[str] = []
    sub = list(parts[start:])
    for i, part in enumerate(sub):
        candidate = current / part
        if candidate.exists():
            try:
                current = candidate.resolve()
            except OSError:
                remaining = sub[i:]
                break
        else:
            remaining = sub[i:]
            break
    else:
        return current
    for part in remaining:
        current = current / part
    return current
