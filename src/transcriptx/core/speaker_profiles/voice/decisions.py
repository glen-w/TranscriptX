"""Decision state reducer for voice match accept/reject/dismiss/promote."""

from __future__ import annotations

from transcriptx.core.speaker_profiles.voice.models import VoiceMatchDecisionV1


def decision_suppresses_suggestion(
    decisions: list[VoiceMatchDecisionV1],
    *,
    candidate_profile_id: str,
    model_generation_id: str,
    reference_corpus_digest: str,
) -> bool:
    """True when an in-scope reject still suppresses re-suggestion.

    Reconsider when generation or corpus digest changed vs rejection-time store.
    Leave-unlinked never writes a decision — callers must not invent one.
    """
    relevant = [
        d
        for d in decisions
        if d.decision_kind == "reject"
        and d.candidate_profile_id == candidate_profile_id
    ]
    if not relevant:
        return False
    latest = max(relevant, key=lambda d: d.created_at)
    if latest.model_generation_id and latest.model_generation_id != model_generation_id:
        return False
    if (
        latest.reference_corpus_digest
        and latest.reference_corpus_digest != reference_corpus_digest
    ):
        return False
    return True


def apply_supersede(
    existing: list[VoiceMatchDecisionV1], new: VoiceMatchDecisionV1
) -> list[VoiceMatchDecisionV1]:
    """Return decisions with ``new`` appended; supersede link recorded on new."""
    return list(existing) + [new]
