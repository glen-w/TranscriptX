"""Insights-page presentation helpers.

Guided / Full controls was trialled and removed; Insights always uses Full
controls density. Caps and helpers below remain for shared layout utilities
and residual Guided-path unit coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

import streamlit as st

InsightsDetailMode = Literal["guided", "full"]

ANALYSIS_PAYLOAD_CACHE_KEY = "_insights_analysis_payload_cache"

# Progressive-disclosure caps (legacy Guided; Full uses higher inline limits)
GUIDED_ANALYSIS_SECTION_CAP = 4
GUIDED_RANKED_ROW_CAP = 5
GUIDED_HIGHLIGHT_CARD_CAP = 5
GUIDED_SUMMARY_PREVIEW_CHARS = 1800
GUIDED_METADATA_CHIP_CAP = 4
GUIDED_MIN_HIGHLIGHT_QUOTE_CHARS = 24
GUIDED_HIGHLIGHT_OVERLAP_IOU = 0.55

# Stable presentation order for language / style / salience blocks
# (used when grouping former Analysis placements).
ANALYSIS_GROUP_ORDER: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "language_profile",
        "Language profile",
        ("lexical_diversity_block", "epistemic_markers_block"),
    ),
    (
        "interaction_style",
        "Interaction style",
        ("politeness_block",),
    ),
    (
        "topics_salience",
        "Topics and salience",
        ("keyphrases_block", "insights_contract"),
    ),
)

_BLOCK_TO_GROUP: dict[str, tuple[str, str]] = {}
for _key, _title, _blocks in ANALYSIS_GROUP_ORDER:
    for _bid in _blocks:
        _BLOCK_TO_GROUP[_bid] = (_key, _title)

MODULE_PLAIN_DESCRIPTIONS: dict[str, str] = {
    "lexical_diversity": (
        "How varied the vocabulary is — higher diversity means more distinct words "
        "relative to length."
    ),
    "epistemic_markers": (
        "How often speakers hedge uncertainty or boost certainty in their wording."
    ),
    "politeness": (
        "How often speakers mark courtesy or soften requests in the conversation."
    ),
    "keyphrases": (
        "The most salient multiword phrases ranked from the transcript wording."
    ),
    "insights": (
        "Content themes and recurring ideas, kept separate from style-of-speech markers."
    ),
}

SUMMARY_TYPE_LABELS: dict[str, str] = {
    "llm_summary": "Transcript Summary",
    "narrative_summary": "Narrative Summary",
    "executive_summary": "Executive Summary",
}


def get_insights_detail_mode() -> InsightsDetailMode:
    """Always Full controls — Guided/Full toggle removed."""
    return "full"


def is_insights_guided() -> bool:
    return False


def is_insights_full() -> bool:
    return True


def analysis_group_for_block(block_id: str) -> tuple[str, str] | None:
    return _BLOCK_TO_GROUP.get(block_id)


def order_analysis_placements(placements: Sequence[Any]) -> list[Any]:
    """Stable group order; known analysis blocks first, then unknowns."""
    by_id = {getattr(p, "block_id", ""): p for p in placements}
    ordered: list[Any] = []
    seen: set[str] = set()
    for _key, _title, block_ids in ANALYSIS_GROUP_ORDER:
        for bid in block_ids:
            p = by_id.get(bid)
            if p is not None:
                ordered.append(p)
                seen.add(bid)
    for p in placements:
        bid = getattr(p, "block_id", "")
        if bid not in seen:
            ordered.append(p)
    return ordered


def analysis_group_headings(
    placements: Sequence[Any],
) -> list[tuple[str, str, list[Any]]]:
    """Return (group_key, group_title, placements) in display order."""
    ordered = order_analysis_placements(placements)
    groups: list[tuple[str, str, list[Any]]] = []
    current_key: str | None = None
    current_title = ""
    bucket: list[Any] = []
    for p in ordered:
        info = analysis_group_for_block(getattr(p, "block_id", ""))
        if info is None:
            key, title = "other", "Other analysis"
        else:
            key, title = info
        if key != current_key:
            if bucket:
                groups.append((current_key or "other", current_title, bucket))
            current_key = key
            current_title = title
            bucket = [p]
        else:
            bucket.append(p)
    if bucket:
        groups.append((current_key or "other", current_title, bucket))
    return groups


@dataclass(frozen=True)
class HighlightCardModel:
    """Normalised highlight card for Guided / Full rendering."""

    event_key: str
    theme_label: str
    speakers: tuple[str, ...]
    start: float
    end: float
    quote: str
    section: str
    score: float | None
    breakdown: dict[str, Any] | None
    segment_index: int | None
    raw_event: dict[str, Any] | None = None


def highlight_quote_eligible(quote: str, *, min_chars: int = GUIDED_MIN_HIGHLIGHT_QUOTE_CHARS) -> bool:
    text = " ".join(str(quote or "").split())
    if len(text) < min_chars:
        return False
    # Reject placeholder / non-prose dumps
    if text.startswith("{") and text.endswith("}"):
        return False
    return True


def _interval_iou(a0: float, a1: float, b0: float, b1: float) -> float:
    start = max(a0, b0)
    end = min(a1, b1)
    inter = max(0.0, end - start)
    if inter <= 0:
        return 0.0
    union = max(a1, b1) - min(a0, b0)
    if union <= 0:
        return 0.0
    return inter / union


def _quote_token_overlap(a: str, b: str) -> float:
    ta = {t for t in a.lower().split() if len(t) > 2}
    tb = {t for t in b.lower().split() if len(t) > 2}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / float(len(ta | tb))


def dedupe_overlapping_highlights(
    cards: Sequence[HighlightCardModel],
    *,
    iou_threshold: float = GUIDED_HIGHLIGHT_OVERLAP_IOU,
    quote_overlap: float = 0.7,
) -> list[HighlightCardModel]:
    """Keep strongest card when time+quote substantially overlap. Deterministic."""
    ranked = sorted(
        cards,
        key=lambda c: (
            -(c.score if c.score is not None else 0.0),
            c.start,
            c.event_key,
        ),
    )
    kept: list[HighlightCardModel] = []
    for card in ranked:
        duplicate = False
        q = " ".join(card.quote.split())
        for prior in kept:
            iou = _interval_iou(card.start, card.end, prior.start, prior.end)
            if iou < iou_threshold:
                continue
            if _quote_token_overlap(q, " ".join(prior.quote.split())) >= quote_overlap:
                duplicate = True
                break
        if not duplicate:
            kept.append(card)
    # Restore chronological for display after strength ranking for selection
    kept.sort(key=lambda c: (-(c.score if c.score is not None else 0.0), c.start, c.event_key))
    return kept


def theme_label_for_user(label: str | None, *, is_unthemed: bool = False) -> str:
    raw = str(label or "").strip()
    if is_unthemed or raw.lower() in {"", "unthemed", "untagged"}:
        return "Other highlights"
    return raw


def truncate_for_preview(text: str, *, limit: int = GUIDED_SUMMARY_PREVIEW_CHARS) -> tuple[str, bool]:
    """Return (preview_or_full, was_truncated). Non-destructive — caller keeps full text."""
    body = text or ""
    if len(body) <= limit:
        return body, False
    # Break on paragraph/sentence when practical
    cut = body[:limit].rsplit("\n\n", 1)[0]
    if len(cut) < limit * 0.5:
        cut = body[:limit].rsplit(". ", 1)[0]
        if cut and not cut.endswith("."):
            cut = cut + "."
    if len(cut) < limit * 0.4:
        cut = body[:limit].rstrip() + "…"
    return cut, True


def compact_metadata_chips(labels: Sequence[str], *, cap: int = GUIDED_METADATA_CHIP_CAP) -> list[str]:
    out: list[str] = []
    for label in labels:
        text = str(label or "").strip()
        if text and text not in out:
            out.append(text)
        if len(out) >= cap:
            break
    return out


def clear_analysis_payload_cache() -> None:
    st.session_state.pop(ANALYSIS_PAYLOAD_CACHE_KEY, None)


def load_cached_analysis_json(
    loader: Any,
    module: str,
    suffix: str,
) -> dict[str, Any] | None:
    """Load each analysis artifact at most once per Analysis render path."""
    cache = st.session_state.setdefault(ANALYSIS_PAYLOAD_CACHE_KEY, {})
    key = f"{module}:{suffix}"
    if key in cache:
        return cache[key]
    payload = None
    if loader is not None:
        try:
            loaded = loader.load_json(module, suffix)
            payload = loaded if isinstance(loaded, dict) else None
        except Exception:
            payload = None
    cache[key] = payload
    return payload


def analysis_payload_has_user_content(module: str, payload: dict[str, Any] | None) -> bool:
    """True when Guided should spend a slot on this optional analysis artifact."""
    if not isinstance(payload, dict) or not payload:
        return False
    if payload.get("usable") is False:
        return False
    if module == "insights":
        themes = payload.get("key_themes") or []
        ideas = payload.get("recurring_ideas") or []
        style = payload.get("style_markers") or {}
        has_theme = any(
            isinstance(r, dict) and str(r.get("phrase") or "").strip() for r in themes
        )
        has_idea = any(
            isinstance(r, dict) and str(r.get("phrase") or "").strip() for r in ideas
        )
        has_style = isinstance(style, dict) and any(
            v not in (None, "", {}, []) for v in style.values()
        )
        return has_theme or has_idea or has_style
    if module == "keyphrases":
        gbm = payload.get("global_by_method") or {}
        nc = gbm.get("noun_chunks") if isinstance(gbm, dict) else None
        phrases = (nc or {}).get("phrases") if isinstance(nc, dict) else None
        return bool(phrases)
    if module in {"lexical_diversity", "epistemic_markers", "politeness"}:
        stats = payload.get("global_stats")
        return isinstance(stats, dict) and bool(stats)
    return True
