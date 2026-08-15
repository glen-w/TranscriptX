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
