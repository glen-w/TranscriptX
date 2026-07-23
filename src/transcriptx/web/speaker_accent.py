"""Shared per-speaker accent colours for the Studio viewer UI.

Overview speaker cards, transcript chips, chart slice headers, and
per-speaker LLM summaries all use the same palette so a speaker keeps
one colour across pages. Accents are stable by normalised display name.
"""

from __future__ import annotations

import html
from contextlib import contextmanager
from hashlib import blake2b
from typing import Iterator

import streamlit as st

# Distinct accents readable on dark and light themes (matches Overview cards).
SPEAKER_ACCENTS = (
    "#5B8DEF",  # blue
    "#E07A5F",  # coral
    "#81B29A",  # sage
    "#F2CC8F",  # gold
    "#9B8BB8",  # lavender
    "#7EB8DA",  # sky
)


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


def speaker_heading_html(
    name: object,
    *,
    meta: str | None = None,
    accent: str | None = None,
    css_class: str = "tx-speaker-heading",
) -> str:
    """Coloured swatch + name (+ optional meta), matching Overview cards."""
    label = str(name or "Speaker").strip() or "Speaker"
    color = accent or speaker_accent_color(label)
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


def speaker_chip_html(name: object, *, accent: str | None = None) -> str:
    """Inline transcript-style chip with per-speaker accent + swatch."""
    label = str(name or "Unknown").strip() or "Unknown"
    color = accent or speaker_accent_color(label)
    return (
        f'<span class="tx-speaker-chip" style="--speaker-accent: {color}">'
        f'<span class="tx-speaker-swatch" aria-hidden="true"></span>'
        f"{html.escape(label)}"
        f"</span>"
    )


def speaker_inline_html(name: object, *, accent: str | None = None) -> str:
    """Compact swatch + bold name for quote / span rows."""
    label = str(name or "").strip()
    if not label:
        return ""
    color = accent or speaker_accent_color(label)
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
) -> str:
    """Compact ``Name · timestamp`` line for transcript Turns/Segments."""
    label = str(name or "Unknown").strip() or "Unknown"
    color = accent or speaker_accent_color(label)
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
) -> Iterator[None]:
    """Expander with a coloured speaker swatch beside the Streamlit label.

    Streamlit expander titles are plain text, so the swatch sits in a
    narrow column to the left of the expander control.
    """
    label = str(name or "Speaker").strip() or "Speaker"
    color = speaker_accent_color(label)
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
