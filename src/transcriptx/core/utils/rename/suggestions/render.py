"""Render rename stems from cues and smart-rename patterns."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from transcriptx.core.utils.rename.smart_name import (
    build_rename_tokens,
    extract_pattern_tokens,
    render_smart_rename,
    resolve_smart_rename_pattern,
)
from transcriptx.core.utils.rename.suggestions.models import RawRenameCue, RenameOption

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug_title(title: str, *, max_len: int = 60) -> str:
    text = (title or "").strip().lower()
    if not text:
        return ""
    slug = _SLUG_RE.sub("_", text).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("_")
    return slug


def _collapse_stem(stem: str) -> str:
    out = stem
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")


def render_stem_from_cue(
    cue: RawRenameCue,
    *,
    pattern: str,
    transcript_stem: str,
    existing_stems: Iterable[str],
) -> RenameOption | None:
    resolved = resolve_smart_rename_pattern(pattern)
    title_slug = slug_title(cue.title)
    tokens: dict[str, str] = {}
    if cue.event_date is not None:
        dt = datetime.combine(cue.event_date, datetime.min.time())
        tokens = build_rename_tokens(dt, stem=transcript_stem)
    tokens["title"] = title_slug
    tokens.setdefault("stem", transcript_stem)
    tokens.setdefault("n", "1")

    has_title_token = "title" in extract_pattern_tokens(resolved)
    if cue.event_date is None and not title_slug:
        return None
    if cue.event_date is None and title_slug:
        stem = title_slug
    elif has_title_token:
        stem = _collapse_stem(
            render_smart_rename(
                resolved,
                tokens,
                existing_stems=existing_stems,
                exclude_stem=transcript_stem,
            )
        )
    else:
        base = render_smart_rename(
            resolved,
            {k: v for k, v in tokens.items() if k != "title"},
            existing_stems=existing_stems,
            exclude_stem=transcript_stem,
        )
        stem = _collapse_stem(f"{base}_{title_slug}" if title_slug else base)

    if not stem:
        return None
    return RenameOption(
        stem=stem,
        basis=cue.basis,
        confidence=cue.confidence,
        detail=cue.detail,
        event_date=cue.event_date,
        title=title_slug or cue.title,
    )


def list_sibling_stems(transcript_path: Path) -> list[str]:
    root = transcript_path.parent
    try:
        return [p.stem for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".json"]
    except OSError:
        return []
