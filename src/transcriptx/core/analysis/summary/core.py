"""Core summary computation (pure logic, no I/O)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List
import re

from transcriptx.core.analysis.highlights.core import (  # type: ignore[import-untyped]
    SegmentLite,
)
from transcriptx.core.analysis.highlights.post_process import (  # type: ignore[import-untyped]
    _label_is_low_information,
    assign_themes,
    stable_quote_id,
)
from transcriptx.core.analysis.phrase_quality import (
    PHRASE_QUALITY_VERSION,
    analyse_phrase,
    resource_fingerprint,
    theme_label_policy,
)
from transcriptx.core.analysis.phrase_quality.analyser import annotations_from_surfaces
from transcriptx.core.analysis.phrase_quality.policies import (
    TIER_ENTITY_PROPN,
    TIER_MULTI_CONTENT_NOUN,
    TIER_STRONG_SINGLE_NOUN,
)
from transcriptx.core.analysis.phrase_quality.scoring import select_diverse_themes
from transcriptx.core.utils.nlp_utils import build_tic_mask
from transcriptx.utils.text_utils import is_named_speaker


def compute_summary(
    highlights: Dict[str, Any], segments: List[SegmentLite], cfg: Any
) -> Dict[str, Any]:
    overview = _build_overview(highlights, segments, cfg)
    key_themes = _build_key_themes(highlights, cfg)
    tension_points = _build_tension_points(highlights, cfg)
    commitments = _extract_commitments(segments, cfg)

    return {
        "overview": overview,
        "key_themes": {"bullets": key_themes},
        "tension_points": {"bullets": tension_points},
        "commitments": {"items": commitments},
        "phrase_quality_version": PHRASE_QUALITY_VERSION,
        "phrase_quality_resource_fingerprint": resource_fingerprint(),
    }


def _themes_payload(highlights: Dict[str, Any]) -> List[Dict[str, Any]]:
    themes = highlights.get("themes")
    if themes:
        return list(themes)
    return [asdict(t) for t in assign_themes(highlights)]


def _build_overview(
    highlights: Dict[str, Any], segments: List[SegmentLite], cfg: Any
) -> Dict[str, Any]:
    named_speakers = {
        seg.speaker_display
        for seg in segments
        if seg.speaker_display and is_named_speaker(seg.speaker_display)
    }
    total_speakers = len(named_speakers)

    themes = _themes_payload(highlights)
    themed = [
        t for t in themes if not t.get("is_unthemed") and (t.get("quote_ids") or [])
    ]
    theme_labels = [str(t.get("label") or "").strip() for t in themed if t.get("label")]
    theme_labels = [
        lbl for lbl in theme_labels if lbl and not _label_is_low_information(lbl)
    ]
    # Prefer noun-tier labels only for the overview focus clause — never fall
    # back to emblematic filler phrases when themes are weak.
    high_tier_labels: List[str] = []
    mask = build_tic_mask()
    for lbl in theme_labels:
        quality = analyse_phrase(
            annotations_from_surfaces(lbl.split()), tic_mask=mask
        )
        decision = theme_label_policy(quality)
        if not decision.include:
            continue
        if decision.preference_tier in {
            TIER_MULTI_CONTENT_NOUN,
            TIER_ENTITY_PROPN,
            TIER_STRONG_SINGLE_NOUN,
        }:
            high_tier_labels.append(lbl)

    if len(high_tier_labels) >= 2:
        focus_text = f"{high_tier_labels[0]} and {high_tier_labels[1]}"
    elif len(high_tier_labels) == 1:
        focus_text = high_tier_labels[0]
    else:
        focus_text = ""

    if focus_text:
        sentence1 = f"This session centered on {focus_text}, with {total_speakers} named speakers."
    else:
        sentence1 = f"This session included {total_speakers} named speakers."

    duration_s = 0.0
    if segments:
        duration_s = max(seg.end for seg in segments) - min(
            seg.start for seg in segments
        )
    if duration_s > 1.0:
        minutes = int(duration_s // 60)
        if minutes > 0:
            sentence1 = sentence1.rstrip(".") + f" across about {minutes} minutes."

    sentences: List[str] = [sentence1]

    events = highlights.get("sections", {}).get("conflict_points", {}).get("events", [])
    if events:
        names_ordered: List[str] = []
        seen: set[str] = set()
        for event in events:
            for p in event.get("participants", []) or []:
                disp = p.get("speaker_display")
                if disp and disp not in seen:
                    seen.add(disp)
                    names_ordered.append(disp)
        if names_ordered:
            n_events = len(events)
            name_part = ", ".join(names_ordered[:4])
            if len(names_ordered) > 4:
                name_part += ", and others"
            tense = "moment was" if n_events == 1 else "moments were"
            sentences.append(
                f"{n_events} tension {tense} detected involving {name_part}."
            )

    cold_items = list(
        highlights.get("sections", {}).get("cold_open", {}).get("items", [])
    )
    cold_items.sort(
        key=lambda it: float((it.get("score") or {}).get("total") or 0.0), reverse=True
    )
    tk = str(highlights.get("transcript_key") or "unknown")
    if cold_items:
        top_cold = cold_items[0]
        qid = stable_quote_id(top_cold, tk)
        opening_theme_label: str | None = None
        for t in themes:
            if t.get("is_unthemed"):
                continue
            if qid in (t.get("quote_ids") or []):
                opening_theme_label = str(t.get("label") or "").strip() or None
                break
        if opening_theme_label:
            sentences.append(f"The opening moments focused on {opening_theme_label}.")

    paragraph = " ".join(s.strip() for s in sentences if s.strip())
    supporting_quotes = (
        highlights.get("sections", {}).get("cold_open", {}).get("items", [])[:2]
    )
    return {"paragraph": paragraph, "supporting_quotes": supporting_quotes}


def _build_key_themes(highlights: Dict[str, Any], cfg: Any) -> List[Dict[str, Any]]:
    phrases = (
        highlights.get("sections", {}).get("emblematic_phrases", {}).get("phrases", [])
    )
    mask = build_tic_mask()
    limit = int(cfg.counts.theme_bullets)

    ranked: List[Dict[str, Any]] = []
    for phrase in phrases:
        text = str(phrase.get("phrase") or "").strip()
        if not text:
            continue
        tokens = [str(t) for t in (phrase.get("tokens") or text.split())]
        quality = analyse_phrase(annotations_from_surfaces(tokens), tic_mask=mask)
        decision = theme_label_policy(quality)
        if not decision.include:
            continue
        ranked.append(
            {
                "text": text,
                "phrase": text,
                "tokens": tokens,
                "canonical_key": phrase.get("canonical_key")
                or quality.features.canonical_key,
                "head_lemma": quality.features.head_lemma,
                "evidence_quotes": phrase.get("examples", []),
                "preference_tier": decision.preference_tier,
                "score_total": float((phrase.get("score") or {}).get("total") or 0.0),
            }
        )

    ranked.sort(
        key=lambda row: (
            int(row["preference_tier"]),
            -float(row["score_total"]),
            -len(row.get("tokens") or []),
            str(row.get("canonical_key") or ""),
        )
    )

    preferred = [
        row
        for row in ranked
        if int(row["preference_tier"])
        in {TIER_MULTI_CONTENT_NOUN, TIER_ENTITY_PROPN, TIER_STRONG_SINGLE_NOUN}
    ]
    pool = preferred if preferred else ranked
    selected = select_diverse_themes(pool, limit=limit)
    return [
        {"text": row["text"], "evidence_quotes": row.get("evidence_quotes") or []}
        for row in selected
    ]


def _build_tension_points(highlights: Dict[str, Any], cfg: Any) -> List[Dict[str, Any]]:
    events = highlights.get("sections", {}).get("conflict_points", {}).get("events", [])
    bullets = []
    for event in events[: cfg.counts.tension_bullets]:
        participants = [p.get("speaker_display") for p in event.get("participants", [])]
        participants_text = ", ".join([p for p in participants if p])
        text = f"Tension spike involving {participants_text}."
        bullets.append(
            {
                "text": text,
                "anchor_quote": event.get("anchor_quote", {}),
                "score_breakdown": event.get("score_breakdown", {}),
            }
        )
    return bullets


def _commitment_has_content(span_text: str) -> bool:
    """Reject light-verb-only stems like 'need to' / 'have to' without an object."""
    surfaces = [t for t in str(span_text or "").casefold().split() if t.isalpha()]
    if len(surfaces) < 3:
        return False
    quality = analyse_phrase(
        annotations_from_surfaces(surfaces), tic_mask=build_tic_mask()
    )
    if not quality.accepted_for_scoring:
        return False
    return quality.features.content_token_count >= 2


def _extract_commitments(segments: List[SegmentLite], cfg: Any) -> List[Dict[str, Any]]:
    rules = cfg.commitments.rules or []
    compiled = [re.compile(rule, re.IGNORECASE) for rule in rules]
    commitments: List[Dict[str, Any]] = []
    owners_seen: Dict[str, int] = {}

    for segment in segments:
        if not segment.text:
            continue
        for rule in compiled:
            match = rule.search(segment.text)
            if not match:
                continue
            owner_display = segment.speaker_display
            if owners_seen.get(owner_display, 0) >= cfg.commitments.max_per_owner:
                continue
            span_text = match.group(0)
            if not _commitment_has_content(span_text):
                continue
            commitment = {
                "action": span_text,
                "owner_display": owner_display,
                "owner_speaker_id": segment.speaker_id,
                "timestamp": {"start": segment.start, "end": segment.end},
                "due": None,
                "confidence": 0.7,
                "evidence_quote": {
                    "speaker": segment.speaker_display,
                    "start": segment.start,
                    "end": segment.end,
                    "quote": segment.text,
                    "segment_refs": {
                        "segment_db_ids": (
                            [segment.segment_db_id] if segment.segment_db_id else []
                        ),
                        "segment_uuids": (
                            [segment.segment_uuid] if segment.segment_uuid else []
                        ),
                        "segment_indexes": [segment.segment_index],
                    },
                },
                "extraction": {
                    "rule_id": rule.pattern,
                    "match_text": span_text,
                    "span_text": span_text,
                    "span_start_char": match.start(),
                    "span_end_char": match.end(),
                    "score_breakdown": {"rule_weight": 1.0},
                },
            }
            commitments.append(commitment)
            owners_seen[owner_display] = owners_seen.get(owner_display, 0) + 1
            if len(commitments) >= cfg.counts.commitments:
                return commitments
            break
    return commitments
