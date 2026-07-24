"""Atomic onboarding checklist preferences."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from transcriptx.core.utils import paths as paths_mod
from transcriptx.io.atomic_json import locked_path, write_bytes_atomic

ONBOARDING_SCHEMA_VERSION = 1
ONBOARDING_FILENAME = "onboarding.json"

ItemState = Literal["pending", "completed", "skipped"]

REQUIRED_ITEM_IDS: tuple[str, ...] = (
    "open_library",
    "import_or_demo",
    "run_analysis",
    "open_insights_charts",
    "export_artifacts",
    "know_guided_full",
)
OPTIONAL_ITEM_IDS: tuple[str, ...] = (
    "external_transcription",
    "optional_ollama",
)
ALL_ITEM_IDS: tuple[str, ...] = REQUIRED_ITEM_IDS + OPTIONAL_ITEM_IDS

ITEM_LABELS: dict[str, str] = {
    "open_library": "Open Library",
    "import_or_demo": "Import a transcript or load the demo",
    "run_analysis": "Run analysis",
    "open_insights_charts": "Open Insights / Charts",
    "export_artifacts": "Export / Artifacts",
    "know_guided_full": "Know Guided vs Full controls",
    "external_transcription": "External transcription (command gen)",
    "optional_ollama": "Optional Ollama",
}

ITEM_PAGES: dict[str, str] = {
    "open_library": "Library",
    "import_or_demo": "Import Transcript",
    "run_analysis": "Run Analysis",
    "open_insights_charts": "Insights",
    "export_artifacts": "Artifacts",
    "know_guided_full": "Settings",
    "external_transcription": "Transcribe Audio",
    "optional_ollama": "Settings",
}

_PREFS_CACHE: dict[str, Any] | None = None


class OnboardingItem(BaseModel):
    state: ItemState = "pending"


class OnboardingPrefs(BaseModel):
    dismissed: bool = False
    items: dict[str, OnboardingItem] = Field(default_factory=dict)


@dataclass
class OnboardingDraft:
    prefs: OnboardingPrefs
    raw_file_revision: str
    recovery: bool = False
    recovery_message: str = ""
    path: Path | None = None


@dataclass
class SaveResult:
    ok: bool
    error: str | None = None
    conflict: bool = False


def onboarding_prefs_path() -> Path:
    return Path(paths_mod.CONFIG_DIR) / ONBOARDING_FILENAME


def raw_file_revision(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prefs_integrity_hash(prefs_dict: dict[str, Any]) -> str:
    payload = json.dumps(prefs_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def built_in_prefs() -> OnboardingPrefs:
    return OnboardingPrefs(
        dismissed=False,
        items={i: OnboardingItem(state="pending") for i in ALL_ITEM_IDS},
    )


def merge_prefs(partial: dict[str, Any] | None) -> OnboardingPrefs:
    base = built_in_prefs()
    if not isinstance(partial, dict):
        return base
    dismissed = partial.get("dismissed", False)
    if not isinstance(dismissed, bool):
        dismissed = False
    items_in = partial.get("items")
    items: dict[str, OnboardingItem] = {}
    for item_id in ALL_ITEM_IDS:
        raw = {}
        if isinstance(items_in, dict):
            raw = items_in.get(item_id) or {}
        if not isinstance(raw, dict):
            raw = {}
        state = raw.get("state", "pending")
        if state not in ("pending", "completed", "skipped"):
            state = "pending"
        if item_id in REQUIRED_ITEM_IDS and state == "skipped":
            state = "pending"
        items[item_id] = OnboardingItem(state=state)  # type: ignore[arg-type]
    return OnboardingPrefs(dismissed=dismissed, items=items)


def derived_complete(prefs: OnboardingPrefs) -> bool:
    for item_id in REQUIRED_ITEM_IDS:
        state = prefs.items.get(item_id, OnboardingItem()).state
        if state != "completed":
            return False
    return True


def _envelope_bytes(prefs: OnboardingPrefs) -> bytes:
    prefs_dict = prefs.model_dump(mode="json")
    envelope = {
        "schema_version": ONBOARDING_SCHEMA_VERSION,
        "prefs": prefs_dict,
        "prefs_hash": prefs_integrity_hash(prefs_dict),
    }
    return (json.dumps(envelope, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load_onboarding_prefs(
    path: Path | None = None,
) -> tuple[OnboardingPrefs, OnboardingDraft]:
    target = path or onboarding_prefs_path()
    if not target.exists():
        prefs = built_in_prefs()
        return prefs, OnboardingDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=raw_file_revision(b""),
            path=target,
        )
    try:
        raw = target.read_bytes()
    except OSError as exc:
        prefs = built_in_prefs()
        return prefs, OnboardingDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=raw_file_revision(b""),
            recovery=True,
            recovery_message=f"Could not read onboarding: {exc}",
            path=target,
        )
    revision = raw_file_revision(raw)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        prefs = built_in_prefs()
        return prefs, OnboardingDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message=f"Malformed onboarding JSON: {exc}",
            path=target,
        )
    if not isinstance(payload, dict):
        prefs = built_in_prefs()
        return prefs, OnboardingDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message="Onboarding file is not a JSON object.",
            path=target,
        )
    if payload.get("schema_version") != ONBOARDING_SCHEMA_VERSION:
        prefs = built_in_prefs()
        return prefs, OnboardingDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message="Unsupported onboarding schema; file preserved.",
            path=target,
        )
    prefs_obj = payload.get("prefs")
    if not isinstance(prefs_obj, dict):
        prefs = built_in_prefs()
        return prefs, OnboardingDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message="Onboarding envelope missing prefs.",
            path=target,
        )
    stored_hash = payload.get("prefs_hash")
    if stored_hash is not None and stored_hash != prefs_integrity_hash(prefs_obj):
        prefs = built_in_prefs()
        return prefs, OnboardingDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message="Onboarding prefs_hash mismatch; file preserved.",
            path=target,
        )
    merged = merge_prefs(prefs_obj)
    return merged, OnboardingDraft(
        prefs=merged.model_copy(deep=True),
        raw_file_revision=revision,
        path=target,
    )


def invalidate_onboarding_cache() -> None:
    global _PREFS_CACHE
    _PREFS_CACHE = None


def get_cached_onboarding_prefs() -> OnboardingPrefs:
    global _PREFS_CACHE
    if _PREFS_CACHE is not None:
        return _PREFS_CACHE["prefs"]
    prefs, _ = load_onboarding_prefs()
    _PREFS_CACHE = {"prefs": prefs}
    return prefs


def save_onboarding_prefs(
    draft: OnboardingDraft, *, path: Path | None = None
) -> SaveResult:
    if draft.recovery:
        return SaveResult(ok=False, error="Save disabled while onboarding is in recovery.")
    target = path or draft.path or onboarding_prefs_path()
    new_bytes = _envelope_bytes(draft.prefs)
    try:
        with locked_path(target):
            current = target.read_bytes() if target.exists() else b""
            if raw_file_revision(current) != draft.raw_file_revision:
                return SaveResult(
                    ok=False,
                    conflict=True,
                    error="Onboarding changed in another session. Reload and retry.",
                )
            write_bytes_atomic(target, new_bytes)
            draft.raw_file_revision = raw_file_revision(new_bytes)
            draft.recovery = False
            draft.recovery_message = ""
            draft.path = target
    except OSError as exc:
        return SaveResult(ok=False, error=str(exc))
    invalidate_onboarding_cache()
    return SaveResult(ok=True)


def set_item_state(item_id: str, state: ItemState) -> SaveResult:
    if item_id not in ALL_ITEM_IDS:
        return SaveResult(ok=False, error=f"Unknown item {item_id}")
    if item_id in REQUIRED_ITEM_IDS and state == "skipped":
        return SaveResult(ok=False, error="Required items cannot be skipped")
    prefs, draft = load_onboarding_prefs()
    if draft.recovery:
        return SaveResult(ok=False, error=draft.recovery_message)
    draft.prefs.items[item_id] = OnboardingItem(state=state)
    return save_onboarding_prefs(draft)


def set_dismissed(dismissed: bool) -> SaveResult:
    prefs, draft = load_onboarding_prefs()
    if draft.recovery:
        return SaveResult(ok=False, error=draft.recovery_message)
    draft.prefs.dismissed = dismissed
    return save_onboarding_prefs(draft)
