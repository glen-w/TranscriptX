"""UI-agnostic transcript path → canonical subject identity resolution."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from transcriptx.core.utils.slug_manager import load_index

SessionResolver = Callable[[str], tuple[str, str] | None]


@dataclass(frozen=True)
class TranscriptContextResolution:
    """Canonical transcript identity derived from a filesystem path."""

    subject_id: str
    run_id: str | None


def tolerant_resolve(path: str | Path) -> str:
    """Normalize a path without failing when the target file is missing."""
    return str(Path(path).expanduser().resolve(strict=False))


def paths_match(left: str | Path, right: str | Path) -> bool:
    """Compare paths tolerantly, including samefile when both exist."""
    try:
        left_path = Path(left).expanduser().resolve(strict=False)
        right_path = Path(right).expanduser().resolve(strict=False)
    except (OSError, RuntimeError, ValueError):
        return str(left) == str(right)
    if left_path == right_path:
        return True
    try:
        if left_path.is_file() and right_path.is_file():
            return os.path.samefile(left_path, right_path)
    except (OSError, ValueError):
        pass
    return False


def _lookup_slug_for_path(normalized_path: str) -> tuple[str | None, list[str]]:
    """Return (slug, run_ids_from_index) for a transcript source path."""
    index = load_index()
    for entry in index.get("transcripts", {}).values():
        source_path = entry.get("source_path", "")
        if not source_path:
            continue
        if paths_match(source_path, normalized_path):
            slug = entry.get("slug")
            runs = entry.get("runs", [])
            run_ids = [str(r) for r in runs] if isinstance(runs, list) else []
            return (str(slug) if slug else None, run_ids)
    return None, []


def _run_dir_name(path: str | Path) -> str:
    return Path(path).name


def _latest_run_from_dirs(run_dirs: Sequence[str | Path]) -> str | None:
    """Pick newest run by mtime; lexical max of dir names if mtime unavailable."""
    if not run_dirs:
        return None

    scored: list[tuple[float, str, str]] = []
    for run_dir in run_dirs:
        name = _run_dir_name(run_dir)
        try:
            mtime = Path(run_dir).stat().st_mtime
            scored.append((mtime, name, name))
        except OSError:
            scored.append((float("-inf"), name, name))

    if not scored:
        return None

    if any(item[0] != float("-inf") for item in scored):
        return max(scored, key=lambda item: (item[0], item[1]))[2]

    return max(scored, key=lambda item: item[1])[2]


def _latest_run_from_ids(
    run_ids: Sequence[str],
    *,
    outputs_slug: str | None,
) -> str | None:
    """Resolve run ids to output dirs when possible and apply mtime ordering."""
    if not run_ids:
        return None
    if outputs_slug:
        from transcriptx.core.utils.paths import OUTPUTS_DIR

        run_dirs = [Path(OUTPUTS_DIR) / outputs_slug / run_id for run_id in run_ids]
        latest = _latest_run_from_dirs(run_dirs)
        if latest is not None:
            return latest
    return max(str(run_id) for run_id in run_ids)


def resolve_transcript_context(
    transcript_path: str | Path,
    *,
    linked_run_dirs: Sequence[str | Path] | None = None,
    slug_hint: str | None = None,
    latest_run_hint: str | None = None,
    session_resolver: SessionResolver | None = None,
) -> TranscriptContextResolution:
    """
    Resolve transcript path to canonical subject_id (slug or raw path) and optional run_id.

    Session lookup is optional and injected by callers; this module does not import Streamlit.
    """
    normalized_path = tolerant_resolve(transcript_path)
    slug: str | None = slug_hint.strip() if slug_hint else None
    index_run_ids: list[str] = []

    if slug is None:
        slug, index_run_ids = _lookup_slug_for_path(normalized_path)

    run_id: str | None = latest_run_hint.strip() if latest_run_hint else None

    if run_id is None and linked_run_dirs:
        run_id = _latest_run_from_dirs(linked_run_dirs)

    if run_id is None and slug and index_run_ids:
        run_id = _latest_run_from_ids(index_run_ids, outputs_slug=slug)

    if slug is not None:
        return TranscriptContextResolution(subject_id=slug, run_id=run_id)

    if session_resolver is not None:
        resolved = session_resolver(normalized_path)
        if resolved is not None:
            resolved_slug, resolved_run = resolved
            return TranscriptContextResolution(
                subject_id=resolved_slug,
                run_id=resolved_run,
            )

    return TranscriptContextResolution(subject_id=normalized_path, run_id=None)
