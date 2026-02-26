"""Core summary computation (pure logic, no I/O)."""

from __future__ import annotations

from typing import Any, Dict, List
import re

from transcriptx.core.analysis.highlights.core import (  # type: ignore[import-untyped]
    SegmentLite,
)


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
    }


def _build_overview(
    highlights: Dict[str, Any], segments: List[SegmentLite], cfg: Any
) -> Dict[str, Any]:
    speakers = {seg.speaker_display for seg in segments if seg.speaker_display}
    total_speakers = len(speakers)
    total_quotes = len(
        highlights.get("sections", {}).get("cold_open", {}).get("items", [])
    )
    phrases = (
        highlights.get("sections", {}).get("emblematic_phrases", {}).get("phrases", [])
    )
    top_phrases = [p.get("phrase") for p in phrases[:3] if p.get("phrase")]
    phrase_text = ", ".join(top_phrases) if top_phrases else "key themes"
    paragraph = (
        f"This session surfaces {total_quotes} notable opening moments across "
        f"{total_speakers} named speakers, centering on {phrase_text}."
    )
    supporting_quotes = (
        highlights.get("sections", {}).get("cold_open", {}).get("items", [])[:2]
    )
    return {"paragraph": paragraph, "supporting_quotes": supporting_quotes}


def _build_key_themes(highlights: Dict[str, Any], cfg: Any) -> List[Dict[str, Any]]:
    phrases = (
        highlights.get("sections", {}).get("emblematic_phrases", {}).get("phrases", [])
    )
    bullets = []
    for phrase in phrases[: cfg.counts.theme_bullets]:
        bullets.append(
            {
                "text": phrase.get("phrase", ""),
                "evidence_quotes": phrase.get("examples", []),
            }
        )
    return bullets


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
