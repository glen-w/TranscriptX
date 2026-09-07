"""Ranked Speaker ID link targets (name/alias/voice/create/none).

Read-only helper for the naming UI. Writes still go through journalled
``SpeakerProfileService`` ops. Voice scores never auto-confirm a link.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

from transcriptx.core.speaker_profiles.aggregates import (
    AppearanceRow,
    ProfileListItem,
)
from transcriptx.core.speaker_profiles.identity import (
    link_file_key,
    local_speaker_key_from_raw,
)
from transcriptx.core.speaker_profiles.models import SpeakerProfileLinkV1


def _normalize_name_key(name: object) -> str:
    return " ".join(str(name or "").strip().split()).casefold()

LinkMode = Literal["none", "create", "existing"]
LinkReason = Literal[
    "already_linked",
    "name_match",
    "alias_match",
    "voice",
    "create",
    "name_only",
]


@dataclass(frozen=True)
class LinkTarget:
    """One selectable destination for a Speaker ID save."""

    mode: LinkMode
    reason: LinkReason
    label: str
    profile_id: str | None = None
    display_name: str = ""
    appearance_count: int = 0
    last_appearance_date: str | None = None
    accent_color: str | None = None
    aliases: tuple[str, ...] = ()
    already_linked: bool = False
    duplicate_name_warning: bool = False
    is_default: bool = False
    detail: str = ""


@dataclass(frozen=True)
class LinkTargetSet:
    """Ranked targets plus the default selection for the naming UI."""

    targets: tuple[LinkTarget, ...]
    default_mode: LinkMode
    default_profile_id: str | None
    managed: bool
    recipe_hint: str | None = None

    def default_target(self) -> LinkTarget | None:
        for target in self.targets:
            if target.is_default:
                return target
        return self.targets[0] if self.targets else None

    def to_workspace_payload(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for target in self.targets:
            rows.append(
                {
                    "mode": target.mode,
                    "reason": target.reason,
                    "label": target.label,
                    "profile_id": target.profile_id,
                    "display_name": target.display_name,
                    "appearance_count": target.appearance_count,
                    "last_appearance_date": target.last_appearance_date,
                    "accent_color": target.accent_color,
                    "aliases": list(target.aliases),
                    "already_linked": target.already_linked,
                    "duplicate_name_warning": target.duplicate_name_warning,
                    "is_default": target.is_default,
                    "detail": target.detail,
                }
            )
        return rows


def resolve_save_link_mode(
    payload: Mapping[str, Any],
    *,
    profile_managed: bool,
) -> tuple[LinkMode, str | None]:
    """Map a save_name payload to ``(link_mode, profile_id)``.

    Additive ``link_mode`` wins. Legacy ``link_profile`` bool maps to ``create``
    when true on a managed transcript, otherwise ``none``.
    """
    raw_mode = str(payload.get("link_mode") or "").strip().casefold()
    profile_id = str(payload.get("profile_id") or "").strip() or None
    if raw_mode in {"none", "create", "existing"}:
        mode: LinkMode = raw_mode  # type: ignore[assignment]
        if mode != "existing":
            profile_id = profile_id if mode == "existing" else None
        if mode == "existing" and not profile_id:
            return "none", None
        if not profile_managed and mode in {"create", "existing"}:
            return "none", None
        return mode, profile_id
    if bool(payload.get("link_profile", False)) and profile_managed:
        return "create", None
    return "none", None


def suggest_link_targets(
    *,
    display_name: str,
    managed: bool,
    listing: Sequence[ProfileListItem] = (),
    appearances_by_profile: Mapping[str, Sequence[AppearanceRow]] | None = None,
    live_link: SpeakerProfileLinkV1 | None = None,
    voice_candidates: Sequence[Mapping[str, Any]] | None = None,
    recipe_hint: str | None = None,
) -> LinkTargetSet:
    """Rank attach/create/name-only options for one occurrence + draft name."""
    name = " ".join((display_name or "").split()).strip()
    name_key = _normalize_name_key(name)
    active = [item for item in listing if item.status == "active"]
    by_id = {item.profile_id: item for item in listing}

    targets: list[LinkTarget] = []
    seen_ids: set[str] = set()

    if live_link is not None:
        owner = by_id.get(live_link.profile_id)
        display = owner.display_name if owner is not None else live_link.profile_id
        targets.append(
            _existing_target(
                item=owner,
                profile_id=live_link.profile_id,
                display_name=display,
                reason="already_linked",
                already_linked=True,
                appearances_by_profile=appearances_by_profile,
                detail="Already linked on this transcript.",
            )
        )
        seen_ids.add(live_link.profile_id)

    name_hits = [
        item
        for item in active
        if item.profile_id not in seen_ids and _name_matches(item, name_key)
    ]
    alias_hits = [
        item
        for item in active
        if item.profile_id not in seen_ids
        and item not in name_hits
        and _alias_matches(item, name_key)
    ]

    for item in name_hits:
        targets.append(
            _existing_target(
                item=item,
                profile_id=item.profile_id,
                display_name=item.display_name,
                reason="name_match",
                already_linked=False,
                appearances_by_profile=appearances_by_profile,
                detail="Display name matches this profile.",
            )
        )
        seen_ids.add(item.profile_id)
    for item in alias_hits:
        targets.append(
            _existing_target(
                item=item,
                profile_id=item.profile_id,
                display_name=item.display_name,
                reason="alias_match",
                already_linked=False,
                appearances_by_profile=appearances_by_profile,
                detail="An alias matches this name.",
            )
        )
        seen_ids.add(item.profile_id)

    for raw in voice_candidates or ():
        pid = str(raw.get("profile_id") or "").strip()
        if not pid or pid in seen_ids:
            continue
        item = by_id.get(pid)
        if item is not None and item.status != "active":
            continue
        display = (
            item.display_name
            if item is not None
            else str(raw.get("display_name") or pid)
        )
        confidence = raw.get("confidence")
        refs = raw.get("reference_count")
        detail_bits = ["Local voice suggestion — confirm to apply."]
        if confidence:
            detail_bits.append(str(confidence))
        if refs is not None:
            detail_bits.append(f"{refs} refs")
        targets.append(
            _existing_target(
                item=item,
                profile_id=pid,
                display_name=display,
                reason="voice",
                already_linked=False,
                appearances_by_profile=appearances_by_profile,
                detail=" · ".join(detail_bits),
            )
        )
        seen_ids.add(pid)

    duplicate_name = bool(name_key) and any(
        _normalize_name_key(item.display_name) == name_key for item in active
    )
    create_label = f"Create new profile: {name}" if name else "Create new profile"
    if managed:
        targets.append(
            LinkTarget(
                mode="create",
                reason="create",
                label=create_label,
                display_name=name,
                duplicate_name_warning=duplicate_name,
                detail=(
                    "A profile with this display name already exists."
                    if duplicate_name
                    else "New longitudinal profile for this speaker."
                ),
            )
        )
    targets.append(
        LinkTarget(
            mode="none",
            reason="name_only",
            label="Name only — this transcript",
            display_name=name,
            detail="Local speaker map only; no profile link.",
        )
    )

    default_mode, default_pid = _pick_default(
        targets=targets,
        managed=managed,
        live_link=live_link,
        unique_name_or_alias=len(name_hits) + len(alias_hits) == 1,
        name_or_alias_id=(
            (name_hits + alias_hits)[0].profile_id
            if len(name_hits) + len(alias_hits) == 1
            else None
        ),
    )
    marked: list[LinkTarget] = []
    for target in targets:
        is_default = target.mode == default_mode and target.profile_id == default_pid
        if is_default != target.is_default:
            marked.append(
                LinkTarget(
                    mode=target.mode,
                    reason=target.reason,
                    label=target.label,
                    profile_id=target.profile_id,
                    display_name=target.display_name,
                    appearance_count=target.appearance_count,
                    last_appearance_date=target.last_appearance_date,
                    accent_color=target.accent_color,
                    aliases=target.aliases,
                    already_linked=target.already_linked,
                    duplicate_name_warning=target.duplicate_name_warning,
                    is_default=is_default,
                    detail=target.detail,
                )
            )
        else:
            marked.append(target)

    hint = recipe_hint
    if not managed:
        hint = (
            recipe_hint
            or "Longitudinal linking is available for managed library transcripts only."
        )

    return LinkTargetSet(
        targets=tuple(marked),
        default_mode=default_mode,
        default_profile_id=default_pid,
        managed=managed,
        recipe_hint=hint,
    )


def live_link_for_occurrence(
    *,
    managed_transcript_id: str | None,
    raw_speaker: str,
    get_live_link,
) -> SpeakerProfileLinkV1 | None:
    """Look up the live link for one occurrence; None when unmanaged or missing."""
    if not managed_transcript_id:
        return None
    try:
        key = link_file_key(
            managed_transcript_id, local_speaker_key_from_raw(raw_speaker)
        )
    except Exception:
        return None
    try:
        return get_live_link(key)
    except Exception:
        return None


def _name_matches(item: ProfileListItem, name_key: str) -> bool:
    if not name_key:
        return False
    return _normalize_name_key(item.display_name) == name_key


def _alias_matches(item: ProfileListItem, name_key: str) -> bool:
    if not name_key:
        return False
    return any(_normalize_name_key(alias) == name_key for alias in item.aliases)


def _last_date(
    profile_id: str,
    appearances_by_profile: Mapping[str, Sequence[AppearanceRow]] | None,
) -> str | None:
    if not appearances_by_profile:
        return None
    rows = appearances_by_profile.get(profile_id) or ()
    dates = [row.appearance_date for row in rows if row.appearance_date is not None]
    if not dates:
        return None
    return max(dates).isoformat()


def _existing_target(
    *,
    item: ProfileListItem | None,
    profile_id: str,
    display_name: str,
    reason: LinkReason,
    already_linked: bool,
    appearances_by_profile: Mapping[str, Sequence[AppearanceRow]] | None,
    detail: str,
) -> LinkTarget:
    count = item.link_count if item is not None else 0
    last = _last_date(profile_id, appearances_by_profile)
    bits = [display_name]
    if count:
        bits.append(f"{count} appearance{'s' if count != 1 else ''}")
    if last:
        bits.append(last)
    return LinkTarget(
        mode="existing",
        reason=reason,
        label=" · ".join(bits),
        profile_id=profile_id,
        display_name=display_name,
        appearance_count=count,
        last_appearance_date=last,
        accent_color=item.accent_color if item is not None else None,
        aliases=item.aliases if item is not None else (),
        already_linked=already_linked,
        detail=detail,
    )


def _pick_default(
    *,
    targets: Sequence[LinkTarget],
    managed: bool,
    live_link: SpeakerProfileLinkV1 | None,
    unique_name_or_alias: bool,
    name_or_alias_id: str | None,
) -> tuple[LinkMode, str | None]:
    if live_link is not None:
        return "existing", live_link.profile_id
    if not managed:
        return "none", None
    if unique_name_or_alias and name_or_alias_id:
        return "existing", name_or_alias_id
    return "create", None
