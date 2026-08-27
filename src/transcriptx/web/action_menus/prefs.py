"""Interface menu preferences: models, sanitise, load/save, draft, recovery."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from transcriptx.core.utils.paths import CONFIG_DIR
from transcriptx.io.atomic_json import locked_path, write_bytes_atomic
from transcriptx.web.action_menus.catalog import (
    ACTIONS_BY_ID,
    SECTION_ALLOWLISTS,
)
from transcriptx.web.action_menus.ids import (
    ACTION_ORDER,
    SECTION_ORDER,
    ActionDisplay,
    ActionDisplaySetting,
    ActionId,
    SectionId,
    SectionMenuMode,
    StandardMenuMode,
)

_GLOBAL_DISPLAY_VALUES: frozenset[str] = frozenset(v.value for v in ActionDisplay)
_SECTION_DISPLAY_VALUES: frozenset[str] = frozenset(
    v.value for v in ActionDisplaySetting
)

INTERFACE_SCHEMA_VERSION = 1
INTERFACE_MENUS_FILENAME = "interface_menus.json"

DRAFT_SESSION_KEY = "interface_menus_draft"
_PREFS_CACHE: dict[str, Any] | None = None


class SectionMenuPrefs(BaseModel):
    show_menu: bool = True
    mode: Literal["use_standard", "section_default", "manual"] = "section_default"
    selected: list[ActionId] = Field(default_factory=list)
    action_display: Literal["inherit", "icon", "text", "both"] = "inherit"


class InterfaceMenuPrefs(BaseModel):
    standard_menu_mode: Literal["built_in", "custom"] = "built_in"
    standard_menu: list[ActionId] = Field(default_factory=list)
    sections: dict[SectionId, SectionMenuPrefs] = Field(default_factory=dict)
    # Instructional ⓘ / Streamlit help= tips. Run-id identity ⓘ stays always on.
    show_info_tooltips: bool = True
    action_display: Literal["icon", "text", "both"] = "both"


@dataclass
class InterfaceDraft:
    prefs: InterfaceMenuPrefs
    raw_file_revision: str  # hash of complete raw bytes at last successful load
    recovery: bool = False
    recovery_message: str = ""
    path: Path | None = None


@dataclass
class SaveResult:
    ok: bool
    error: str | None = None
    conflict: bool = False


def interface_menus_path() -> Path:
    return CONFIG_DIR / INTERFACE_MENUS_FILENAME


def raw_file_revision(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prefs_integrity_hash(prefs_dict: dict[str, Any]) -> str:
    payload = json.dumps(prefs_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sanitise_global_action_display(raw: Any) -> ActionDisplay:
    value = raw.value if isinstance(raw, ActionDisplay) else raw
    if value in _GLOBAL_DISPLAY_VALUES:
        return ActionDisplay(value)
    return ActionDisplay.BOTH


def sanitise_section_action_display(
    raw: Any, *, default: ActionDisplaySetting = ActionDisplaySetting.INHERIT
) -> ActionDisplaySetting:
    value = raw.value if isinstance(raw, ActionDisplaySetting) else raw
    if value in _SECTION_DISPLAY_VALUES:
        return ActionDisplaySetting(value)
    return default


def resolve_action_display(
    prefs: InterfaceMenuPrefs, section: SectionId
) -> ActionDisplay:
    """Resolve inherit against the global default; invalid values fall back to both."""
    section_prefs = prefs.sections.get(section)
    setting = (
        sanitise_section_action_display(section_prefs.action_display)
        if section_prefs is not None
        else ActionDisplaySetting.INHERIT
    )
    if setting is ActionDisplaySetting.INHERIT:
        return sanitise_global_action_display(prefs.action_display)
    return ActionDisplay(setting.value)


def sanitise_action_ids(raw: list[Any] | None) -> list[ActionId]:
    """Keep known ActionIds, drop duplicates, preserve first-seen then catalogue order."""
    if not raw:
        return []
    wanted: set[ActionId] = set()
    for item in raw:
        try:
            if isinstance(item, ActionId):
                aid = item
            else:
                aid = ActionId(str(item))
        except ValueError:
            continue
        if aid in ACTIONS_BY_ID:
            wanted.add(aid)
    return [a for a in ACTION_ORDER if a in wanted]


def built_in_prefs() -> InterfaceMenuPrefs:
    sections = {
        sid: SectionMenuPrefs(
            show_menu=True,
            mode=SectionMenuMode.SECTION_DEFAULT.value,
            selected=[],
            action_display=ActionDisplaySetting.INHERIT.value,
        )
        for sid in SECTION_ORDER
    }
    return InterfaceMenuPrefs(
        standard_menu_mode=StandardMenuMode.BUILT_IN.value,
        standard_menu=[],
        sections=sections,
        show_info_tooltips=True,
        action_display=ActionDisplay.BOTH.value,
    )


def merge_prefs(partial: dict[str, Any] | None) -> InterfaceMenuPrefs:
    """Merge file payload onto built-ins; normalise known sections."""
    base = built_in_prefs()
    if not isinstance(partial, dict):
        return base

    mode = partial.get("standard_menu_mode", "built_in")
    if mode not in ("built_in", "custom"):
        mode = "built_in"
    standard = sanitise_action_ids(partial.get("standard_menu"))

    sections_in = partial.get("sections")
    if not isinstance(sections_in, dict):
        sections_in = {}

    sections: dict[SectionId, SectionMenuPrefs] = {}
    for sid in SECTION_ORDER:
        raw = sections_in.get(sid.value) or sections_in.get(sid)
        if not isinstance(raw, dict):
            sections[sid] = base.sections[sid]
            continue
        smode = raw.get("mode", "section_default")
        if smode not in ("use_standard", "section_default", "manual"):
            smode = "section_default"
        selected = sanitise_action_ids(raw.get("selected"))
        # Keep only allowlisted selections
        allow = set(SECTION_ALLOWLISTS[sid])
        selected = [a for a in selected if a in allow]
        show = raw.get("show_menu", True)
        if not isinstance(show, bool):
            show = True
        built_display = sanitise_section_action_display(
            base.sections[sid].action_display
        )
        if "action_display" not in raw:
            display = built_display
        else:
            display = sanitise_section_action_display(
                raw.get("action_display"), default=built_display
            )
        sections[sid] = SectionMenuPrefs(
            show_menu=show,
            mode=smode,
            selected=selected,
            action_display=display.value,
        )

    show_tips = partial.get("show_info_tooltips", True)
    if not isinstance(show_tips, bool):
        show_tips = True
    if "action_display" not in partial:
        global_display = sanitise_global_action_display(base.action_display)
    else:
        global_display = sanitise_global_action_display(partial.get("action_display"))

    return InterfaceMenuPrefs(
        standard_menu_mode=mode,  # type: ignore[arg-type]
        standard_menu=standard,
        sections=sections,
        show_info_tooltips=show_tips,
        action_display=global_display.value,
    )


def _envelope_bytes(prefs: InterfaceMenuPrefs) -> bytes:
    prefs_dict = prefs.model_dump(mode="json")
    # Ensure canonical section key order in serialisation
    ordered_sections = {
        sid.value: prefs_dict["sections"][sid.value]
        for sid in SECTION_ORDER
        if sid.value in prefs_dict["sections"]
    }
    prefs_dict["sections"] = ordered_sections
    envelope = {
        "schema_version": INTERFACE_SCHEMA_VERSION,
        "prefs": prefs_dict,
        "prefs_hash": prefs_integrity_hash(prefs_dict),
    }
    return (json.dumps(envelope, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load_interface_prefs(
    path: Path | None = None,
) -> tuple[InterfaceMenuPrefs, InterfaceDraft]:
    """Load prefs. Returns (effective_prefs_for_runtime, draft_state)."""
    target = path or interface_menus_path()
    if not target.exists():
        prefs = built_in_prefs()
        draft = InterfaceDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=raw_file_revision(b""),
            recovery=False,
            path=target,
        )
        return prefs, draft

    try:
        raw = target.read_bytes()
    except OSError as exc:
        prefs = built_in_prefs()
        draft = InterfaceDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=raw_file_revision(b""),
            recovery=True,
            recovery_message=f"Could not read interface menus: {exc}",
            path=target,
        )
        return prefs, draft

    revision = raw_file_revision(raw)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        prefs = built_in_prefs()
        draft = InterfaceDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message=f"Malformed interface menus JSON: {exc}",
            path=target,
        )
        return prefs, draft

    if not isinstance(payload, dict):
        prefs = built_in_prefs()
        draft = InterfaceDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message="Interface menus file is not a JSON object.",
            path=target,
        )
        return prefs, draft

    schema = payload.get("schema_version")
    if schema != INTERFACE_SCHEMA_VERSION:
        prefs = built_in_prefs()
        draft = InterfaceDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message=(
                f"Unsupported interface menus schema_version={schema!r} "
                f"(expected {INTERFACE_SCHEMA_VERSION}). File preserved."
            ),
            path=target,
        )
        return prefs, draft

    prefs_obj = payload.get("prefs")
    if not isinstance(prefs_obj, dict):
        prefs = built_in_prefs()
        draft = InterfaceDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message="Interface menus envelope missing prefs object.",
            path=target,
        )
        return prefs, draft

    stored_hash = payload.get("prefs_hash")
    recomputed = prefs_integrity_hash(prefs_obj)
    if stored_hash is not None and stored_hash != recomputed:
        prefs = built_in_prefs()
        draft = InterfaceDraft(
            prefs=prefs.model_copy(deep=True),
            raw_file_revision=revision,
            recovery=True,
            recovery_message="Interface menus prefs_hash mismatch; file preserved.",
            path=target,
        )
        return prefs, draft

    merged = merge_prefs(prefs_obj)
    draft = InterfaceDraft(
        prefs=merged.model_copy(deep=True),
        raw_file_revision=revision,
        recovery=False,
        path=target,
    )
    return merged, draft


def invalidate_prefs_cache() -> None:
    global _PREFS_CACHE
    _PREFS_CACHE = None


def get_cached_runtime_prefs() -> InterfaceMenuPrefs:
    global _PREFS_CACHE
    if _PREFS_CACHE is not None:
        return _PREFS_CACHE["prefs"]
    prefs, _ = load_interface_prefs()
    _PREFS_CACHE = {"prefs": prefs}
    return prefs


def save_interface_prefs(
    draft: InterfaceDraft,
    *,
    path: Path | None = None,
) -> SaveResult:
    """Atomic compare-and-swap save using raw-file revision under locks."""
    if draft.recovery:
        return SaveResult(
            ok=False,
            error="Save disabled while interface menus file is in recovery state.",
        )

    target = path or draft.path or interface_menus_path()
    new_bytes = _envelope_bytes(draft.prefs)

    try:
        with locked_path(target):
            if target.exists():
                current = target.read_bytes()
            else:
                current = b""
            current_rev = raw_file_revision(current)
            if current_rev != draft.raw_file_revision:
                return SaveResult(
                    ok=False,
                    conflict=True,
                    error=(
                        "Interface menus were changed in another session. "
                        "Reload saved settings, then re-apply your edits."
                    ),
                )
            write_bytes_atomic(target, new_bytes)
            draft.raw_file_revision = raw_file_revision(new_bytes)
            draft.recovery = False
            draft.recovery_message = ""
            draft.path = target
    except OSError as exc:
        return SaveResult(ok=False, error=f"Could not save interface menus: {exc}")

    invalidate_prefs_cache()
    return SaveResult(ok=True)


def replace_with_built_in_defaults(
    draft: InterfaceDraft,
    *,
    path: Path | None = None,
) -> SaveResult:
    """Recovery write: backup old file, write built-ins, clear recovery."""
    target = path or draft.path or interface_menus_path()
    prefs = built_in_prefs()
    new_bytes = _envelope_bytes(prefs)

    try:
        with locked_path(target):
            if target.exists():
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                backup = target.with_name(f"{target.name}.bak.{stamp}")
                shutil.copy2(target, backup)
            write_bytes_atomic(target, new_bytes)
            draft.prefs = prefs.model_copy(deep=True)
            draft.raw_file_revision = raw_file_revision(new_bytes)
            draft.recovery = False
            draft.recovery_message = ""
            draft.path = target
    except OSError as exc:
        return SaveResult(ok=False, error=f"Could not replace interface menus: {exc}")

    invalidate_prefs_cache()
    return SaveResult(ok=True)


def hydrate_draft_from_disk(
    session_state: dict[str, Any], *, path: Path | None = None
) -> InterfaceDraft:
    _, draft = load_interface_prefs(path)
    session_state[DRAFT_SESSION_KEY] = draft
    return draft


def reset_draft_to_built_ins(session_state: dict[str, Any]) -> InterfaceDraft:
    """Restore: unsaved draft only; preserves recovery flag and baseline."""
    existing = session_state.get(DRAFT_SESSION_KEY)
    recovery = False
    recovery_message = ""
    revision = raw_file_revision(b"")
    path = interface_menus_path()
    if isinstance(existing, InterfaceDraft):
        recovery = existing.recovery
        recovery_message = existing.recovery_message
        revision = existing.raw_file_revision
        path = existing.path or path
    draft = InterfaceDraft(
        prefs=built_in_prefs(),
        raw_file_revision=revision,
        recovery=recovery,
        recovery_message=recovery_message,
        path=path,
    )
    session_state[DRAFT_SESSION_KEY] = draft
    return draft


def reload_draft_from_disk(
    session_state: dict[str, Any], *, path: Path | None = None
) -> InterfaceDraft:
    return hydrate_draft_from_disk(session_state, path=path)


def get_or_hydrate_draft(
    session_state: dict[str, Any], *, path: Path | None = None
) -> InterfaceDraft:
    existing = session_state.get(DRAFT_SESSION_KEY)
    if isinstance(existing, InterfaceDraft):
        return existing
    return hydrate_draft_from_disk(session_state, path=path)


def validate_draft_for_save(prefs: InterfaceMenuPrefs) -> str | None:
    """Return error message if an enabled section would have an empty allowlist intersection."""
    from transcriptx.web.action_menus.resolve import configured_actions_for_section

    for sid in SECTION_ORDER:
        section = prefs.sections[sid]
        if not section.show_menu:
            continue
        # Validation uses a synthetic "primary" context: transcript + has_run
        # for sections that need it; catalogue invariants guarantee section_default
        # is non-empty. Manual/custom still need non-empty allowlist intersection.
        configured = configured_actions_for_section(
            prefs,
            sid,
            subject_type="transcript",
            has_run=True,
            apply_capabilities=False,
        )
        if not configured:
            return (
                f"Section “{sid.value}” has Show menu on but no allowed actions "
                f"for the selected mode. Choose at least one action or turn Show menu off."
            )
    return None
