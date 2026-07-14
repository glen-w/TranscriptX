"""Review ranking confidence from evidence (never mutates rule confidence)."""

from __future__ import annotations

from typing import Optional

from transcriptx.services.corrections_studio.schema import (
    CandidateEvidence,
    EvidenceSignal,
    EvidenceStrength,
)

_BASE = {
    EvidenceStrength.strong: 0.85,
    EvidenceStrength.moderate: 0.65,
    EvidenceStrength.weak: 0.45,
    EvidenceStrength.disputed: 0.35,
}


def ranking_confidence_from_evidence(
    evidence: Optional[CandidateEvidence],
) -> float:
    if evidence is None:
        return 0.5
    score = float(_BASE.get(evidence.strength, 0.5))
    signals = set(evidence.signals or [])
    if EvidenceSignal.memory_match in signals:
        score += 0.05
    if EvidenceSignal.repeated_form in signals:
        score += 0.03
    if signals == {EvidenceSignal.model_suggestion} or signals == set():
        if EvidenceSignal.model_suggestion in signals and len(signals) == 1:
            score -= 0.10
    return max(0.05, min(0.95, score))


def evidence_for_detector_kind(kind: str) -> CandidateEvidence:
    if kind == "memory_hit":
        return CandidateEvidence(
            strength=EvidenceStrength.strong,
            signals=[EvidenceSignal.memory_match],
            review_priority="high",
        )
    if kind == "acronym":
        return CandidateEvidence(
            strength=EvidenceStrength.strong,
            signals=[EvidenceSignal.acronym_pattern],
            review_priority="high",
        )
    if kind == "consistency":
        return CandidateEvidence(
            strength=EvidenceStrength.moderate,
            signals=[
                EvidenceSignal.cross_segment_consistency,
                EvidenceSignal.repeated_form,
            ],
            review_priority="normal",
        )
    if kind == "fuzzy":
        return CandidateEvidence(
            strength=EvidenceStrength.moderate,
            signals=[EvidenceSignal.speaker_context],
            review_priority="normal",
        )
    return CandidateEvidence(
        strength=EvidenceStrength.weak,
        signals=[EvidenceSignal.model_suggestion],
        review_priority="inspect",
    )


def merge_evidence(
    *items: Optional[CandidateEvidence],
    disputed: bool = False,
) -> CandidateEvidence:
    strengths: list[EvidenceStrength] = []
    signals: list[EvidenceSignal] = []
    rationale_parts: list[str] = []
    certainty = None
    priority = "normal"
    for ev in items:
        if ev is None:
            continue
        strengths.append(ev.strength)
        for s in ev.signals:
            if s not in signals:
                signals.append(s)
        if ev.rationale:
            rationale_parts.append(ev.rationale[:500])
        if ev.model_certainty_label:
            certainty = ev.model_certainty_label
        if ev.review_priority == "high":
            priority = "high"
        elif ev.review_priority == "inspect" and priority != "high":
            priority = "inspect"
    if disputed:
        strength = EvidenceStrength.disputed
        priority = "inspect"
    elif EvidenceSignal.memory_match in signals:
        strength = EvidenceStrength.strong
    elif EvidenceStrength.strong in strengths:
        strength = EvidenceStrength.strong
    elif EvidenceStrength.moderate in strengths:
        strength = EvidenceStrength.moderate
    elif EvidenceStrength.weak in strengths:
        strength = EvidenceStrength.weak
    else:
        strength = EvidenceStrength.moderate
    rationale = " | ".join(rationale_parts)[:500]
    return CandidateEvidence(
        strength=strength,
        signals=signals,
        rationale=rationale,
        review_priority=priority,  # type: ignore[arg-type]
        model_certainty_label=certainty,
    )
