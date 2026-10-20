"""Resolve effective unnamed-speaker ungate for a pipeline run."""

from __future__ import annotations


def resolve_allow_unnamed_speakers(*, per_run: bool = False) -> bool:
    """
    Return True when modules should treat diarized labels as eligible speakers.

    Effective rule: per-run option OR global ``analysis.allow_unnamed_speakers``.
    Both default False (skip until speakers are named).
    """
    if per_run:
        return True
    try:
        from transcriptx.core.utils.config import get_config

        return bool(getattr(get_config().analysis, "allow_unnamed_speakers", False))
    except Exception:
        return False


def resolve_treat_as_single_speaker(*, per_run: bool = False) -> bool:
    """Per-run or global ``analysis.treat_as_single_speaker`` (T1 monologue opt-in)."""
    if per_run:
        return True
    try:
        from transcriptx.core.utils.config import get_config

        return bool(getattr(get_config().analysis, "treat_as_single_speaker", False))
    except Exception:
        return False


def effective_speaker_ungate_for_pipeline(
    *,
    allow_unnamed: bool,
    treat_as_single: bool,
    turn_taking_speaker_count: int | None,
) -> bool:
    """Whether diarized labels count for module eligibility (pipeline context var)."""
    if allow_unnamed:
        return True
    if treat_as_single and turn_taking_speaker_count == 1:
        return True
    return False


def use_turn_taking_speaker_gate(
    *,
    allow_unnamed_speakers: bool,
    treat_as_single_speaker: bool,
    turn_taking_speaker_count: int | None,
) -> bool:
    """Whether speaker-count gates use turn-taking labels instead of named counts."""
    if allow_unnamed_speakers:
        return True
    if (
        treat_as_single_speaker
        and turn_taking_speaker_count is not None
        and turn_taking_speaker_count == 1
    ):
        return True
    return False
