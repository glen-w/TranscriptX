"""Shared per-speaker accent colours for the Studio viewer UI.

Overview speaker cards, transcript chips, chart slice headers, and
per-speaker LLM summaries all use the same palette so a speaker keeps
one colour across pages. Assigned profile accents override name-hash.
"""

from __future__ import annotations

import html
from contextlib import contextmanager
from dataclasses import dataclass, field
from hashlib import blake2b
from typing import Iterable, Iterator, Mapping

import streamlit as st

from transcriptx.core.speaker_profiles.accents import (
    SPEAKER_ACCENTS,
    is_safe_accent_css,
    normalize_accent_color,
)
from transcriptx.core.speaker_profiles.errors import SpeakerProfileContractError

__all__ = [
    "SPEAKER_ACCENTS",
    "AccentResolveContext",
    "build_accent_context_from_profiles",
    "normalize_speaker_key",
    "resolve_speaker_accent",
    "speaker_accent_color",
    "speaker_chip_html",
    "speaker_expander",
    "speaker_heading_html",
    "speaker_inline_html",
    "speaker_meta_line_html",
]


@dataclass(frozen=True)
class AccentResolveContext:
    """Optional lookup maps for profile-owned accents."""

    by_name: Mapping[str, str] = field(default_factory=dict)
    by_local_key: Mapping[str, str] = field(default_factory=dict)


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


def build_accent_context_from_profiles(
    profiles: Iterable[object],
    *,
    links: Iterable[object] | None = None,
) -> AccentResolveContext:
    """Build name/alias and optional local-key → accent maps (lowest profile_id wins)."""
    items = sorted(
        (
            p
            for p in profiles
            if getattr(p, "status", None) == "active"
            and getattr(p, "accent_color", None)
        ),
        key=lambda p: str(getattr(p, "profile_id", "")),
    )
    by_name: dict[str, str] = {}
    accent_by_profile: dict[str, str] = {}
    for profile in items:
        color = getattr(profile, "accent_color", None)
        if not color:
            continue
        safe = _safe_css_color(str(color))
        if not safe:
            continue
        pid = str(getattr(profile, "profile_id", ""))
        if pid:
            accent_by_profile[pid] = safe
        names = [getattr(profile, "display_name", "")]
        names.extend(list(getattr(profile, "aliases", ()) or ()))
        for raw in names:
            key = normalize_speaker_key(raw)
            if key and key not in by_name:
                by_name[key] = safe

    by_local: dict[str, str] = {}
    if links is not None:
        # Prefer lowest profile_id among links sharing a local key.
        candidates: dict[str, list[tuple[str, str]]] = {}
        for link in links:
            pid = str(getattr(link, "profile_id", "") or "")
            local = normalize_diarized_key(getattr(link, "local_speaker_key", ""))
            accent = accent_by_profile.get(pid)
            if not local or not accent:
                continue
            candidates.setdefault(local, []).append((pid, accent))
        for local, pairs in candidates.items():
            pairs.sort(key=lambda t: t[0])
            by_local[local] = pairs[0][1]

    return AccentResolveContext(by_name=by_name, by_local_key=by_local)


def speaker_heading_html(
    name: object,
    *,
    meta: str | None = None,
    accent: str | None = None,
    css_class: str = "tx-speaker-heading",
    context: AccentResolveContext | None = None,
    local_speaker_key: str | None = None,
) -> str:
    """Coloured swatch + name (+ optional meta), matching Overview cards."""
    label = str(name or "Speaker").strip() or "Speaker"
    color = resolve_speaker_accent(
        label, accent=accent, context=context, local_speaker_key=local_speaker_key
    )
    meta_html = ""
    if meta:
        meta_html = (
            f'<span class="tx-speaker-heading-meta">'
            f"{html.escape(meta)}</span>"
        )
    return (
        f'<div class="{html.escape(css_class, quote=True)}" '
        f'style="--speaker-accent: {color}">'
        f'<span class="tx-speaker-swatch" aria-hidden="true"></span>'
        f"<strong>{html.escape(label)}</strong>"
        f"{meta_html}"
        f"</div>"
    )


def speaker_chip_html(
    name: object,
    *,
    accent: str | None = None,
    context: AccentResolveContext | None = None,
    local_speaker_key: str | None = None,
) -> str:
    """Inline transcript-style chip with per-speaker accent + swatch."""
    label = str(name or "Unknown").strip() or "Unknown"
    color = resolve_speaker_accent(
        label, accent=accent, context=context, local_speaker_key=local_speaker_key
    )
    return (
        f'<span class="tx-speaker-chip" style="--speaker-accent: {color}">'
        f'<span class="tx-speaker-swatch" aria-hidden="true"></span>'
        f"{html.escape(label)}"
        f"</span>"
    )


def speaker_inline_html(
    name: object,
    *,
    accent: str | None = None,
    context: AccentResolveContext | None = None,
    local_speaker_key: str | None = None,
) -> str:
    """Compact swatch + bold name for quote / span rows."""
    label = str(name or "").strip()
    if not label:
        return ""
    color = resolve_speaker_accent(
        label, accent=accent, context=context, local_speaker_key=local_speaker_key
    )
    return (
        f'<span class="tx-speaker-inline" style="--speaker-accent: {color}">'
        f'<span class="tx-speaker-swatch" aria-hidden="true"></span>'
        f"<strong>{html.escape(label)}</strong>"
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
) -> str:
    """Compact ``Name · timestamp`` line for transcript Turns/Segments."""
    label = str(name or "Unknown").strip() or "Unknown"
    color = resolve_speaker_accent(
        label, accent=accent, context=context, local_speaker_key=local_speaker_key
    )
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
