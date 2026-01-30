"""
Resolve analysis targets into concrete transcript paths and optional TranscriptSet.

This is the single choke point for handling different analysis targets.
Downstream code should only work with resolved paths + optional TranscriptSet.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from transcriptx.core.domain.transcript_set import TranscriptSet

AnalysisTarget = Union[str, TranscriptSet, List[str]]


def resolve_analysis_target(
    target: AnalysisTarget,
    resolver: Optional[Callable[[str], str]] = None,
    name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[List[str], Optional[TranscriptSet]]:
    """
    Resolve analysis target to a list of transcript paths and optional TranscriptSet.

    Args:
        target: Transcript path, TranscriptSet, or list of transcript paths.
        resolver: Optional resolver for transcript IDs to paths.
        name: Optional name for ad-hoc TranscriptSet.
        metadata: Optional metadata for ad-hoc TranscriptSet.

    Returns:
        Tuple of (resolved_paths, transcript_set).
    """
    if isinstance(target, TranscriptSet):
        return target.resolve_transcripts(resolver), target

    if isinstance(target, list):
        normalized = [str(item) for item in target]
        transcript_set = TranscriptSet.create(
            transcript_ids=normalized,
            name=name,
            metadata=metadata,
        )
        return transcript_set.resolve_transcripts(resolver), transcript_set

    if isinstance(target, str):
        return [target], None

    raise TypeError(
        "Unsupported analysis target type. Expected str, TranscriptSet, or list[str]."
    )
