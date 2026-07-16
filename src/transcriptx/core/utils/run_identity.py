"""Shared validators and newest-run ordering for analysis run directories."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

# Production run_id patterns:
#   transcript: YYYYMMDD_HHMMSS_{8 digit ms}
#   group:      YYYYMMDD_HHMMSS_{8 hex}
# Also allow override IDs that are safe path segments (no separators / traversal).
_RUN_ID_PRODUCTION = re.compile(r"^\d{8}_\d{6}_[0-9a-fA-F]{8}$")
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")
_SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")

# Reserved subject / segment names under output roots
_RESERVED_NAMES = frozenset(
    {
        "groups",
        ".cleanup_staging",
        ".transcriptx_index.json",
        ".",
        "..",
    }
)


def is_valid_transcript_slug(value: str) -> bool:
    """Return True if value is a structurally valid transcript output slug."""
    if not value or value in _RESERVED_NAMES or value.startswith("."):
        return False
    if "/" in value or "\\" in value or value in (".", ".."):
        return False
    return bool(_SLUG_PATTERN.fullmatch(value))


def is_valid_group_uuid(value: str) -> bool:
    """Return True if value is a UUID string suitable as a group subject id."""
    if not value or value.startswith("."):
        return False
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def is_valid_run_id(value: str) -> bool:
    """Return True if value is a structurally valid production run_id segment."""
    if not value or value in _RESERVED_NAMES or value.startswith("."):
        return False
    if "/" in value or "\\" in value:
        return False
    if _RUN_ID_PRODUCTION.fullmatch(value):
        return True
    # Allow safe override IDs used in tests / run_id_override
    return bool(_SAFE_SEGMENT.fullmatch(value))


def newest_run_sort_key(
    *,
    mtime_ns: int | None,
    run_id: str,
    path: Path | str | None = None,
) -> tuple[int, str, str]:
    """Sort key for newest-first ordering (negate mtime for reverse=False use).

    Primary: mtime_ns (higher = newer). Missing mtime sorts as oldest (0).
    Tie-breakers: run_id descending (lexicographic reverse via inverted compare
    when used with reverse=True on the full key — see ``newest_run_sort_key_desc``).

    Prefer ``newest_run_sort_key_desc`` for ``list.sort(reverse=False)`` newest-first.
    """
    return (mtime_ns or 0, run_id, str(path or ""))


def newest_run_sort_key_desc(
    *,
    mtime_ns: int | None,
    run_id: str,
    path: Path | str | None = None,
) -> tuple:
    """Key for ``sorted(..., reverse=True)`` / ``sort(reverse=True)`` newest-first.

    Order: higher mtime_ns first; on tie higher run_id string first; then path.
    """
    return (mtime_ns or 0, run_id, str(path or ""))


def run_summary_newest_key(run: Any) -> tuple:
    """Newest-first key for RunSummary-like objects (mtime seconds or ns)."""
    mtime_ns = getattr(run, "mtime_ns", None)
    if mtime_ns is None:
        last = getattr(run, "last_updated", None)
        if last is not None:
            # last_updated historically float seconds
            mtime_ns = int(float(last) * 1_000_000_000)
    run_id = getattr(run, "run_id", "") or ""
    path = getattr(run, "run_root", None) or ""
    return newest_run_sort_key_desc(mtime_ns=mtime_ns, run_id=run_id, path=path)
