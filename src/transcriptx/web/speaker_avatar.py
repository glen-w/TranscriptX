"""Fixed-size speaker avatar chip (photo or initials fallback)."""

from __future__ import annotations

import base64
import html
import re

from transcriptx.core.speaker_profiles.avatars import DATA_URL_MAX_BYTES
from transcriptx.web.speaker_accent import (
    AccentResolveContext,
    resolve_speaker_accent,
)

_CHIP_PX = 40


def speaker_initials(name: object) -> str:
    label = str(name or "").strip()
    if not label:
        return "?"
    parts = [p for p in re.split(r"\s+", label) if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][:2].upper()


def speaker_avatar_chip_html(
    name: object,
    *,
    accent: str | None = None,
    image_bytes: bytes | None = None,
    content_type: str = "image/webp",
    context: AccentResolveContext | None = None,
    local_speaker_key: str | None = None,
    size_px: int = _CHIP_PX,
) -> str:
    """Always same-size circular chip: photo or accent+initials."""
    label = str(name or "Speaker").strip() or "Speaker"
    color = resolve_speaker_accent(
        label, accent=accent, context=context, local_speaker_key=local_speaker_key
    )
    size = max(24, min(128, int(size_px)))
    inner: str
    if image_bytes and len(image_bytes) <= DATA_URL_MAX_BYTES:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        safe_ct = html.escape(content_type or "image/webp", quote=True)
        inner = (
            f'<img class="tx-speaker-avatar-img" alt="" '
            f'src="data:{safe_ct};base64,{b64}" />'
        )
    else:
        initials = html.escape(speaker_initials(label))
        inner = f'<span class="tx-speaker-avatar-initials">{initials}</span>'
    return (
        f'<span class="tx-speaker-avatar" '
        f'style="--speaker-accent: {color}; --tx-avatar-size: {size}px" '
        f'title="{html.escape(label, quote=True)}">'
        f"{inner}"
        f"</span>"
    )


def speaker_heading_with_avatar_html(
    name: object,
    *,
    meta: str | None = None,
    accent: str | None = None,
    image_bytes: bytes | None = None,
    content_type: str = "image/webp",
    context: AccentResolveContext | None = None,
    local_speaker_key: str | None = None,
) -> str:
    label = str(name or "Speaker").strip() or "Speaker"
    color = resolve_speaker_accent(
        label, accent=accent, context=context, local_speaker_key=local_speaker_key
    )
    chip = speaker_avatar_chip_html(
        label,
        accent=accent,
        image_bytes=image_bytes,
        content_type=content_type,
        context=context,
        local_speaker_key=local_speaker_key,
        size_px=40,
    )
    meta_html = ""
    if meta:
        meta_html = (
            f'<span class="tx-speaker-heading-meta">'
            f"{html.escape(meta)}</span>"
        )
    return (
        f'<div class="tx-speaker-heading" style="--speaker-accent: {color}">'
        f"{chip}"
        f"<strong>{html.escape(label)}</strong>"
        f"{meta_html}"
        f"</div>"
    )
