"""List analysis run directories that never reached a terminal run_results.json.

This is a filesystem inventory for operators (Diagnostics). It does not
delete anything and does not consult processing_state.json.

Live vs interrupted uses the analysis lock (flock): ``run_status=running``
plus a held lock is in-progress; running with a free lock is interrupted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from transcriptx.core.utils.analysis_locks import analysis_lock_held
from transcriptx.core.utils.paths import PATHS

RUN_RESULTS_NAME = "run_results.json"

IncompleteState = Literal["missing", "interrupted", "in_progress"]


@dataclass(frozen=True)
class IncompleteRun:
    """A run workspace that is missing terminal execution truth."""

    slug: str
    run_id: str
    run_dir: Path
    kind: str  # "transcript" | "group"
    state: IncompleteState = "missing"


def _iter_slug_dirs(outputs_dir: Path, *, skip: Path | None) -> list[Path]:
    if not outputs_dir.is_dir():
        return []
    skip_resolved: Path | None = None
    if skip is not None:
        try:
            skip_resolved = skip.resolve()
        except OSError:
            skip_resolved = None
    found: list[Path] = []
    for child in sorted(outputs_dir.iterdir(), key=lambda p: p.name):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if skip_resolved is not None:
            try:
                if child.resolve() == skip_resolved:
                    continue
            except OSError:
                if child.name == skip.name:
                    continue
        elif skip is not None and child.name == skip.name:
            continue
        found.append(child)
    return found


def _read_run_results_obj(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _lock_identity_from_payload(
    payload: dict[str, Any], *, kind: str, slug: str
) -> tuple[str, str] | None:
    lock_meta = payload.get("analysis_lock")
    if isinstance(lock_meta, dict):
        lock_kind = str(lock_meta.get("kind") or kind).strip()
        identity = str(lock_meta.get("identity") or "").strip()
        if lock_kind in {"transcript", "group"} and identity:
            return lock_kind, identity
    if kind == "group" and slug:
        return "group", slug
    return None


def _classify_run_dir(
    run_dir: Path,
    *,
    slug: str,
    kind: str,
    state_dir: Path | None = None,
) -> IncompleteState | None:
    results_path = run_dir / RUN_RESULTS_NAME
    if not results_path.is_file():
        return "missing"
    payload = _read_run_results_obj(results_path)
    if payload is None:
        return "missing"
    status = str(payload.get("run_status") or "").strip().lower()
    if status != "running":
        return None
    lock_info = _lock_identity_from_payload(payload, kind=kind, slug=slug)
    if lock_info is None:
        return "interrupted"
    lock_kind, identity = lock_info
    try:
        held = analysis_lock_held(
            kind=lock_kind,  # type: ignore[arg-type]
            identity=identity,
            state_dir=state_dir,
        )
    except Exception:
        return "interrupted"
    return "in_progress" if held else "interrupted"


def _incomplete_under(
    parent: Path,
    *,
    slug: str,
    kind: str,
    state_dir: Path | None = None,
) -> list[IncompleteRun]:
    rows: list[IncompleteRun] = []
    if not parent.is_dir():
        return rows
    for run_dir in sorted(parent.iterdir(), key=lambda p: p.name):
        if not run_dir.is_dir() or run_dir.name.startswith("."):
            continue
        state = _classify_run_dir(
            run_dir, slug=slug, kind=kind, state_dir=state_dir
        )
        if state is None:
            continue
        rows.append(
            IncompleteRun(
                slug=slug,
                run_id=run_dir.name,
                run_dir=run_dir,
                kind=kind,
                state=state,
            )
        )
    return rows


def list_incomplete_run_dirs(
    *,
    outputs_dir: Path | None = None,
    group_outputs_dir: Path | None = None,
    state_dir: Path | None = None,
) -> tuple[IncompleteRun, ...]:
    """Return run dirs that are missing, interrupted, or still in progress."""
    outputs = Path(outputs_dir) if outputs_dir is not None else PATHS.outputs_dir
    groups = (
        Path(group_outputs_dir)
        if group_outputs_dir is not None
        else PATHS.group_outputs_dir
    )
    rows: list[IncompleteRun] = []
    for slug_dir in _iter_slug_dirs(outputs, skip=groups):
        rows.extend(
            _incomplete_under(
                slug_dir, slug=slug_dir.name, kind="transcript", state_dir=state_dir
            )
        )
    if groups.is_dir():
        for group_dir in _iter_slug_dirs(groups, skip=None):
            rows.extend(
                _incomplete_under(
                    group_dir, slug=group_dir.name, kind="group", state_dir=state_dir
                )
            )
    return tuple(rows)
