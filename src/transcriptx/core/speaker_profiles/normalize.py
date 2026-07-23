"""Shared profile field normalization for create/update writes."""

from __future__ import annotations

from dataclasses import dataclass

from transcriptx.core.speaker_profiles.accents import normalize_accent_color
from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError
from transcriptx.core.speaker_profiles.models import SpeakerProfileV1

MAX_ALIASES = 20
MAX_ALIAS_LENGTH = 80


@dataclass(frozen=True)
class NormalizedProfileFields:
    display_name: str
    aliases: list[str]
    notes: str | None
    accent_color: str | None


def normalize_display_name(display_name: str) -> str:
    name = " ".join(str(display_name or "").strip().split())
    if not name:
        raise SpeakerProfileContractError("display_name must be non-empty")
    return name


def normalize_aliases(
    aliases: list[str] | None, *, display_name: str
) -> list[str]:
    """Trim, drop empties, case-insensitive dedupe, drop display-name matches."""
    if aliases is None:
        return []
    display_key = display_name.casefold()
    out: list[str] = []
    seen: set[str] = set()
    for raw in aliases:
        alias = " ".join(str(raw or "").strip().split())
        if not alias:
            continue
        if len(alias) > MAX_ALIAS_LENGTH:
            raise SpeakerProfileContractError(
                f"alias exceeds {MAX_ALIAS_LENGTH} characters"
            )
        key = alias.casefold()
        if key == display_key or key in seen:
            continue
        seen.add(key)
        out.append(alias)
        if len(out) > MAX_ALIASES:
            raise SpeakerProfileContractError(
                f"at most {MAX_ALIASES} aliases allowed"
            )
    return out


def normalize_profile_fields(
    *,
    display_name: str,
    aliases: list[str] | None = None,
    notes: str | None = None,
    accent_color: str | None = None,
) -> NormalizedProfileFields:
    name = normalize_display_name(display_name)
    normalized_aliases = normalize_aliases(aliases, display_name=name)
    accent: str | None = None
    if accent_color is not None:
        accent = normalize_accent_color(accent_color)
    return NormalizedProfileFields(
        display_name=name,
        aliases=normalized_aliases,
        notes=notes,
        accent_color=accent,
    )


def apply_profile_update(
    current: SpeakerProfileV1,
    *,
    display_name: str | None = None,
    aliases: list[str] | None = None,
    notes: str | None = None,
    clear_notes: bool = False,
    accent_color: str | None = None,
    clear_accent: bool = False,
) -> SpeakerProfileV1:
    """Build a validated updated profile from partial update fields."""
    if clear_notes and notes is not None:
        raise SpeakerProfileContractError(
            "cannot pass notes and clear_notes together"
        )
    if clear_accent and accent_color is not None:
        raise SpeakerProfileContractError(
            "cannot pass accent_color and clear_accent together"
        )

    name = (
        normalize_display_name(display_name)
        if display_name is not None
        else current.display_name
    )
    next_aliases = (
        normalize_aliases(aliases, display_name=name)
        if aliases is not None
        else list(current.aliases)
    )
    if aliases is None and display_name is not None:
        # Re-filter aliases that now match the new display name.
        next_aliases = normalize_aliases(next_aliases, display_name=name)

    if clear_notes:
        next_notes: str | None = None
    elif notes is not None:
        next_notes = notes
    else:
        next_notes = current.notes

    if clear_accent:
        next_accent: str | None = None
    elif accent_color is not None:
        next_accent = normalize_accent_color(accent_color)
    else:
        next_accent = current.accent_color

    updated = current.model_copy(
        update={
            "display_name": name,
            "aliases": next_aliases,
            "notes": next_notes,
            "accent_color": next_accent,
        }
    )
    return SpeakerProfileV1.model_validate(updated.model_dump(mode="python"))
