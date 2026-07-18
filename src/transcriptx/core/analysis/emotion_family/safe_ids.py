"""Bounded safe identifier validation for emotion-family paths."""

from __future__ import annotations

import re
from pathlib import Path

_GENERATION_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def is_generation_id(value: str) -> bool:
    return bool(_GENERATION_ID_RE.fullmatch(str(value or "")))


def assert_generation_id(value: str) -> str:
    sid = str(value or "")
    if not is_generation_id(sid):
        raise ValueError(
            f"unsafe generation_id {sid!r}; expected 32 lowercase hex characters"
        )
    return sid


def assert_safe_token(value: str, *, what: str = "token") -> str:
    token = str(value or "")
    if not _SAFE_TOKEN_RE.fullmatch(token):
        raise ValueError(f"unsafe {what}: {token!r}")
    if token in {".", ".."} or "/" in token or "\\" in token:
        raise ValueError(f"unsafe {what}: {token!r}")
    return token


def assert_path_under_root(path: Path, root: Path) -> Path:
    """Resolve path and require it stays under root (blocks symlink escape)."""
    root_resolved = root.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(
            f"path escapes module root: {resolved} not under {root_resolved}"
        ) from exc
    return resolved
