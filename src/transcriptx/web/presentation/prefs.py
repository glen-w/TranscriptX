"""Atomic presentation-mode prefs (Guided / Full controls).

Mirrors ``action_menus/prefs.py``: schema envelope, integrity hash, locked
atomic writes, recovery without overwriting corrupt/unsupported files, and
compare-and-swap concurrent-write protection.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from transcriptx.core.utils import paths as paths_mod
from transcriptx.io.atomic_json import locked_path, write_bytes_atomic

PRESENTATION_SCHEMA_VERSION = 1
PRESENTATION_FILENAME = "presentation_mode.json"

MODE_GUIDED: Literal["guided"] = "guided"
MODE_FULL: Literal["full_controls"] = "full_controls"
PresentationMode = Literal["guided", "full_controls"]
VALID_MODES: frozenset[str] = frozenset({MODE_GUIDED, MODE_FULL})

DRAFT_SESSION_KEY = "presentation_mode_draft"
_PREFS_CACHE: dict[str, Any] | None = None


class PresentationPrefs(BaseModel):
    mode: PresentationMode = Field(default=MODE_GUIDED)


@dataclass
class PresentationDraft:
    prefs: PresentationPrefs
    raw_file_revision: str
    recovery: bool = False
    recovery_message: str = ""
    path: Path | None = None


@dataclass
class SaveResult:
    ok: bool
    error: str | None = None
    conflict: bool = False


def presentation_prefs_path() -> Path:
    return Path(paths_mod.CONFIG_DIR) / PRESENTATION_FILENAME


def raw_file_revision(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prefs_integrity_hash(prefs_dict: dict[str, Any]) -> str:
    payload = json.dumps(prefs_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def built_in_prefs(*, mode: PresentationMode = MODE_GUIDED) -> PresentationPrefs:
    return PresentationPrefs(mode=mode)


def merge_prefs(partial: dict[str, Any] | None) -> PresentationPrefs:
    if not isinstance(partial, dict):
        return built_in_prefs()
    mode = partial.get("mode", MODE_GUIDED)
    if mode not in VALID_MODES:
        mode = MODE_GUIDED
    return PresentationPrefs(mode=mode)  # type: ignore[arg-type]


def _envelope_bytes(prefs: PresentationPrefs) -> bytes:
    prefs_dict = prefs.model_dump(mode="json")
    envelope = {
        "schema_version": PRESENTATION_SCHEMA_VERSION,
        "prefs": prefs_dict,
        "prefs_hash": prefs_integrity_hash(prefs_dict),
    }
    return (json.dumps(envelope, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load_presentation_prefs(
    path: Path | None = None,
) -> tuple[PresentationPrefs, PresentationDraft]:
    """Load prefs. Returns (effective runtime prefs, draft state)."""
    target = path or presentation_prefs_path()
    if not target.exists():
        prefs = built_in_prefs()
        return prefs, PresentationDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=raw_file_revision(b""),
            path=target,
        )

    try:
        raw = target.read_bytes()
    except OSError as exc:
        prefs = built_in_prefs()
        return prefs, PresentationDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=raw_file_revision(b""),
            recovery=True,
            recovery_message=f"Could not read presentation mode: {exc}",
            path=target,
        )

    revision = raw_file_revision(raw)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        prefs = built_in_prefs()
        return prefs, PresentationDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message=f"Malformed presentation mode JSON: {exc}",
            path=target,
        )

    if not isinstance(payload, dict):
        prefs = built_in_prefs()
        return prefs, PresentationDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message="Presentation mode file is not a JSON object.",
            path=target,
        )

    schema = payload.get("schema_version")
    if schema != PRESENTATION_SCHEMA_VERSION:
        prefs = built_in_prefs()
        return prefs, PresentationDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message=(
                f"Unsupported presentation mode schema_version={schema!r} "
                f"(expected {PRESENTATION_SCHEMA_VERSION}). File preserved."
            ),
            path=target,
        )

    prefs_obj = payload.get("prefs")
    if not isinstance(prefs_obj, dict):
        prefs = built_in_prefs()
        return prefs, PresentationDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message="Presentation mode envelope missing prefs object.",
            path=target,
        )

    stored_hash = payload.get("prefs_hash")
    recomputed = prefs_integrity_hash(prefs_obj)
    if stored_hash is not None and stored_hash != recomputed:
        prefs = built_in_prefs()
        return prefs, PresentationDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message="Presentation mode prefs_hash mismatch; file preserved.",
            path=target,
        )

    merged = merge_prefs(prefs_obj)
    return merged, PresentationDraft(
        prefs=merged.model_copy(deep=True),
        raw_file_revision=revision,
        path=target,
    )


def invalidate_presentation_cache() -> None:
    global _PREFS_CACHE
    _PREFS_CACHE = None


def get_cached_presentation_prefs() -> PresentationPrefs:
    global _PREFS_CACHE
    if _PREFS_CACHE is not None:
        return _PREFS_CACHE["prefs"]
    prefs, _ = load_presentation_prefs()
    _PREFS_CACHE = {"prefs": prefs}
    return prefs


def save_presentation_prefs(
    draft: PresentationDraft,
    *,
    path: Path | None = None,
) -> SaveResult:
    if draft.recovery:
        return SaveResult(
            ok=False,
            error="Save disabled while presentation mode file is in recovery state.",
        )

    target = path or draft.path or presentation_prefs_path()
    new_bytes = _envelope_bytes(draft.prefs)
    try:
        with locked_path(target):
            current = target.read_bytes() if target.exists() else b""
            if raw_file_revision(current) != draft.raw_file_revision:
                return SaveResult(
                    ok=False,
                    conflict=True,
                    error=(
                        "Presentation mode was changed in another session. "
                        "Reload, then try again."
                    ),
                )
            write_bytes_atomic(target, new_bytes)
            draft.raw_file_revision = raw_file_revision(new_bytes)
            draft.recovery = False
            draft.recovery_message = ""
            draft.path = target
    except OSError as exc:
        return SaveResult(ok=False, error=f"Could not save presentation mode: {exc}")

    invalidate_presentation_cache()
    return SaveResult(ok=True)


def replace_with_built_in_defaults(
    draft: PresentationDraft,
    *,
    path: Path | None = None,
    mode: PresentationMode = MODE_GUIDED,
) -> SaveResult:
    target = path or draft.path or presentation_prefs_path()
    prefs = built_in_prefs(mode=mode)
    new_bytes = _envelope_bytes(prefs)
    try:
        with locked_path(target):
            if target.exists():
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                shutil.copy2(target, target.with_name(f"{target.name}.bak.{stamp}"))
            write_bytes_atomic(target, new_bytes)
            draft.prefs = prefs.model_copy(deep=True)
            draft.raw_file_revision = raw_file_revision(new_bytes)
            draft.recovery = False
            draft.recovery_message = ""
            draft.path = target
    except OSError as exc:
        return SaveResult(
            ok=False, error=f"Could not replace presentation mode: {exc}"
        )

    invalidate_presentation_cache()
    return SaveResult(ok=True)
