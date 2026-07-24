"""Shared per-speaker accent colours for the Studio viewer UI.

Overview speaker cards, transcript chips, chart slice headers, and
per-speaker LLM summaries all use the same palette so a speaker keeps
one colour across pages. Assigned profile accents override name-hash.
When a speaker resolves to a longitudinal profile, names can deep-link
to the Speakers page via ``?speaker_profile=<id>``.
"""

from __future__ import annotations

import html
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import blake2b
from typing import Iterable, Iterator, Mapping
from urllib.parse import quote

import streamlit as st

from transcriptx.core.speaker_profiles.accents import (
    SPEAKER_ACCENTS,
    is_safe_accent_css,
    normalize_accent_color,
)
from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError

SPEAKER_PROFILE_QUERY_KEY = "speaker_profile"

__all__ = [
    "SPEAKER_ACCENTS",
    "AccentResolveContext",
    "SPEAKER_PROFILE_QUERY_KEY",
    "build_accent_context_from_profiles",
    "load_accent_resolve_context",
    "normalize_speaker_key",
    "resolve_speaker_accent",
    "resolve_speaker_profile_id",
    "speaker_accent_color",
    "speaker_chip_html",
    "speaker_expander",
    "speaker_heading_html",
    "speaker_inline_html",
    "speaker_meta_line_html",
    "speaker_profile_href",
]


@dataclass(frozen=True)
class AccentResolveContext:
    """Optional lookup maps for profile-owned accents and Speakers deep links."""

    by_name: Mapping[str, str] = field(default_factory=dict)
    by_local_key: Mapping[str, str] = field(default_factory=dict)
    profile_id_by_name: Mapping[str, str] = field(default_factory=dict)
    profile_id_by_local_key: Mapping[str, str] = field(default_factory=dict)


def normalize_speaker_key(name: object) -> str:
    return " ".join(str(name or "").strip().split()).casefold()


def speaker_accent_color(name_or_index: object) -> str:
    """Return a palette colour for a speaker name or a display-rank index."""
    if isinstance(name_or_index, int):
        return SPEAKER_ACCENTS[name_or_index % len(SPEAKER_ACCENTS)]
    key = normalize_speaker_key(name_or_index)
    if not key:
        return SPEAKER_ACCENTS[0]
    digest = blake2b(key.encode("utf-8"), digest_size=4).digest()
    return SPEAKER_ACCENTS[int.from_bytes(digest, "big") % len(SPEAKER_ACCENTS)]


def _safe_css_color(color: str) -> str | None:
    try:
        normalized = normalize_accent_color(color)
    except SpeakerProfileContractError:
        return None
    return normalized if is_safe_accent_css(normalized) else None


def normalize_diarized_key(key: object) -> str:
    from transcriptx.io.speaker_map_resolver import normalize_diarized_id

    return normalize_diarized_id(key) or ""


def resolve_speaker_accent(
    name: object,
    *,
    accent: str | None = None,
    local_speaker_key: str | None = None,
    context: AccentResolveContext | None = None,
) -> str:
    """Resolve accent: explicit → linked/local → name/alias map → name hash."""
    if accent:
        safe = _safe_css_color(accent)
        if safe:
            return safe
    ctx = context or AccentResolveContext()
    if local_speaker_key:
        mapped = ctx.by_local_key.get(normalize_diarized_key(local_speaker_key))
        if mapped:
            safe = _safe_css_color(mapped)
            if safe:
                return safe
    key = normalize_speaker_key(name)
    if key and key in ctx.by_name:
        safe = _safe_css_color(ctx.by_name[key])
        if safe:
            return safe
    return speaker_accent_color(name)


def resolve_speaker_profile_id(
    name: object,
    *,
    profile_id: str | None = None,
    local_speaker_key: str | None = None,
    context: AccentResolveContext | None = None,
) -> str | None:
    """Resolve Speakers-page profile id: explicit → local key → name/alias."""
    if profile_id and str(profile_id).strip():
        return str(profile_id).strip()
    ctx = context or AccentResolveContext()
    if local_speaker_key:
        mapped = ctx.profile_id_by_local_key.get(
            normalize_diarized_key(local_speaker_key)
        )
        if mapped:
            return mapped
    key = normalize_speaker_key(name)
    if key and key in ctx.profile_id_by_name:
        return ctx.profile_id_by_name[key]
    return None


def speaker_profile_href(profile_id: str) -> str:
    """Relative query deep-link consumed by the Speakers page router."""
    return f"?{SPEAKER_PROFILE_QUERY_KEY}={quote(str(profile_id).strip(), safe='')}"


def build_accent_context_from_profiles(
    profiles: Iterable[object],
    *,
    links: Iterable[object] | None = None,
) -> AccentResolveContext:
    """Build name/alias and optional local-key → accent/profile_id maps.

    Lowest ``profile_id`` wins for colliding names/aliases. Accent maps only
    include active profiles that have a safe ``accent_color``; profile-id maps
    include all active profiles (so names stay linkable without a custom colour).
    """
    items = sorted(
        (p for p in profiles if getattr(p, "status", None) == "active"),
        key=lambda p: str(getattr(p, "profile_id", "")),
    )
    by_name: dict[str, str] = {}
    profile_id_by_name: dict[str, str] = {}
    accent_by_profile: dict[str, str] = {}
    for profile in items:
        pid = str(getattr(profile, "profile_id", "") or "").strip()
        if not pid:
            continue
        color = getattr(profile, "accent_color", None)
        safe = _safe_css_color(str(color)) if color else None
        if safe:
            accent_by_profile[pid] = safe
        names = [getattr(profile, "display_name", "")]
        names.extend(list(getattr(profile, "aliases", ()) or ()))
        for raw in names:
            key = normalize_speaker_key(raw)
            if not key:
                continue
            if key not in profile_id_by_name:
                profile_id_by_name[key] = pid
            if safe and key not in by_name:
                by_name[key] = safe

    by_local: dict[str, str] = {}
    profile_id_by_local: dict[str, str] = {}
    if links is not None:
        # Prefer lowest profile_id among links sharing a local key.
        accent_candidates: dict[str, list[tuple[str, str]]] = {}
        id_candidates: dict[str, list[str]] = {}
        for link in links:
            pid = str(getattr(link, "profile_id", "") or "").strip()
            local = normalize_diarized_key(getattr(link, "local_speaker_key", ""))
            if not local or not pid:
                continue
            id_candidates.setdefault(local, []).append(pid)
            accent = accent_by_profile.get(pid)
            if accent:
                accent_candidates.setdefault(local, []).append((pid, accent))
        for local, pairs in accent_candidates.items():
            pairs.sort(key=lambda t: t[0])
            by_local[local] = pairs[0][1]
        for local, pids in id_candidates.items():
            pids_sorted = sorted(set(pids))
            profile_id_by_local[local] = pids_sorted[0]

    return AccentResolveContext(
        by_name=by_name,
        by_local_key=by_local,
        profile_id_by_name=profile_id_by_name,
        profile_id_by_local_key=profile_id_by_local,
    )


def _linked_name_html(
    label: str,
    *,
    profile_id: str | None,
    wrap_tag: str = "strong",
) -> str:
    escaped = html.escape(label)
    if not profile_id:
        return f"<{wrap_tag}>{escaped}</{wrap_tag}>" if wrap_tag else escaped
    href = html.escape(speaker_profile_href(profile_id), quote=True)
    title = html.escape(f"Open speaker profile: {label}", quote=True)
    inner = f"<{wrap_tag}>{escaped}</{wrap_tag}>" if wrap_tag else escaped
    return (
        f'<a class="tx-speaker-profile-link" href="{href}" '
        f'title="{title}">{inner}</a>'
    )


def speaker_heading_html(
    name: object,
    *,
    meta: str | None = None,
    accent: str | None = None,
    css_class: str = "tx-speaker-heading",
    context: AccentResolveContext | None = None,
    local_speaker_key: str | None = None,
    profile_id: str | None = None,
) -> str:
    """Coloured swatch + name (+ optional meta), matching Overview cards."""
    label = str(name or "Speaker").strip() or "Speaker"
    color = resolve_speaker_accent(
        label, accent=accent, context=context, local_speaker_key=local_speaker_key
    )
    resolved_pid = resolve_speaker_profile_id(
        label,
        profile_id=profile_id,
        context=context,
        local_speaker_key=local_speaker_key,
    )
    meta_html = ""
    if meta:
        meta_html = (
            f'<span class="tx-speaker-heading-meta">'
            f"{html.escape(meta)}</span>"
        )
    name_html = _linked_name_html(label, profile_id=resolved_pid, wrap_tag="strong")
    return (
        f'<div class="{html.escape(css_class, quote=True)}" '
        f'style="--speaker-accent: {color}">'
        f'<span class="tx-speaker-swatch" aria-hidden="true"></span>'
        f"{name_html}"
        f"{meta_html}"
        f"</div>"
    )


def speaker_chip_html(
    name: object,
    *,
    accent: str | None = None,
    context: AccentResolveContext | None = None,
    local_speaker_key: str | None = None,
    profile_id: str | None = None,
) -> str:
    """Inline transcript-style chip with per-speaker accent + swatch."""
    label = str(name or "Unknown").strip() or "Unknown"
    color = resolve_speaker_accent(
        label, accent=accent, context=context, local_speaker_key=local_speaker_key
    )
    resolved_pid = resolve_speaker_profile_id(
        label,
        profile_id=profile_id,
        context=context,
        local_speaker_key=local_speaker_key,
    )
    name_html = _linked_name_html(label, profile_id=resolved_pid, wrap_tag="")
    return (
        f'<span class="tx-speaker-chip" style="--speaker-accent: {color}">'
        f'<span class="tx-speaker-swatch" aria-hidden="true"></span>'
        f"{name_html}"
        f"</span>"
    )


def speaker_inline_html(
    name: object,
    *,
    accent: str | None = None,
    context: AccentResolveContext | None = None,
    local_speaker_key: str | None = None,
    profile_id: str | None = None,
) -> str:
    """Compact swatch + bold name for quote / span rows."""
    label = str(name or "").strip()
    if not label:
        return ""
    color = resolve_speaker_accent(
        label, accent=accent, context=context, local_speaker_key=local_speaker_key
    )
    resolved_pid = resolve_speaker_profile_id(
        label,
        profile_id=profile_id,
        context=context,
        local_speaker_key=local_speaker_key,
    )
    name_html = _linked_name_html(label, profile_id=resolved_pid, wrap_tag="strong")
    return (
        f'<span class="tx-speaker-inline" style="--speaker-accent: {color}">'
        f'<span class="tx-speaker-swatch" aria-hidden="true"></span>'
        f"{name_html}"
        f"</span>"
    )


def speaker_meta_line_html(
    name: object,
    *,
    timestamp: str | None = None,
    marker_html: str = "",
    accent: str | None = None,
    context: AccentResolveContext | None = None,
    local_speaker_key: str | None = None,
    profile_id: str | None = None,
) -> str:
    """Compact ``Name · timestamp`` line for transcript Turns/Segments."""
    label = str(name or "Unknown").strip() or "Unknown"
    color = resolve_speaker_accent(
        label, accent=accent, context=context, local_speaker_key=local_speaker_key
    )
    resolved_pid = resolve_speaker_profile_id(
        label,
        profile_id=profile_id,
        context=context,
        local_speaker_key=local_speaker_key,
    )
    if resolved_pid:
        href = html.escape(speaker_profile_href(resolved_pid), quote=True)
        title = html.escape(f"Open speaker profile: {label}", quote=True)
        name_html = (
            f'<a class="tx-speaker-name tx-speaker-profile-link" '
            f'href="{href}" title="{title}" '
            f'style="--speaker-accent: {color}">'
            f"{html.escape(label)}</a>"
        )
    else:
        name_html = (
            f'<span class="tx-speaker-name" style="--speaker-accent: {color}">'
            f"{html.escape(label)}</span>"
        )
    line = f"{name_html}{marker_html}"
    if timestamp:
        line = (
            f"{line} · "
            f'<span class="tx-speaker-time">{html.escape(timestamp)}</span>'
        )
    return (
        f'<div class="tx-turn-header" style="--speaker-accent: {color}">'
        f"{line}"
        f"</div>"
    )


@contextmanager
def speaker_expander(
    name: object,
    *,
    meta: str | None = None,
    expanded: bool = False,
    accent: str | None = None,
    context: AccentResolveContext | None = None,
) -> Iterator[None]:
    """Expander with a coloured speaker swatch beside the Streamlit label."""
    label = str(name or "Speaker").strip() or "Speaker"
    color = resolve_speaker_accent(label, accent=accent, context=context)
    title = f"{label} ({meta})" if meta else label
    swatch, body = st.columns([0.045, 0.955], vertical_alignment="center")
    with swatch:
        st.markdown(
            (
                f'<div class="tx-speaker-expander-swatch" '
                f'style="--speaker-accent: {color}">'
                f'<span class="tx-speaker-swatch" aria-hidden="true"></span>'
                f"</div>"
            ),
            unsafe_allow_html=True,
        )
    with body:
        with st.expander(title, expanded=expanded):
            yield


def load_accent_resolve_context() -> AccentResolveContext | None:
    """Best-effort load of active profile accents/ids for Studio surfaces.

    Returns ``None`` when the profiles tree is unavailable or unreadable so
    callers can fall back to name-hash colours without linking.
    """
    try:
        from transcriptx.core.speaker_profiles.layout import (
            links_dir,
            profiles_dir,
            speaker_profiles_dir,
        )
        from transcriptx.core.speaker_profiles.models import (
            SpeakerProfileLinkV1,
            SpeakerProfileV1,
        )
        from transcriptx.core.speaker_profiles.store_io import parse_model

        root = speaker_profiles_dir()
        pref = profiles_dir(root)
        profiles: list[object] = []
        if pref.is_dir():
            for path in pref.glob("*.speaker_profile.json"):
                try:
                    profiles.append(parse_model(SpeakerProfileV1, path))
                except Exception:
                    continue
        link_items: list[object] = []
        lref = links_dir(root)
        if lref.is_dir():
            for path in lref.glob("*.speaker_link.json"):
                try:
                    link_items.append(parse_model(SpeakerProfileLinkV1, path))
                except Exception:
                    continue
        if not profiles and not link_items:
            return AccentResolveContext()
        return build_accent_context_from_profiles(profiles, links=link_items)
    except Exception:
        return None

