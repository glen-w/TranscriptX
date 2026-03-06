"""
Base interfaces for group aggregation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Protocol

from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


class AggregationModule(Protocol):
    """
    Protocol for group aggregation modules.

    Aggregators must operate only on structured per-transcript results.
    They must not open transcript files or re-run NLP.
    """

    def aggregate(
        self,
        per_transcript_results: List[PerTranscriptResult],
        canonical_speaker_map: CanonicalSpeakerMap,
        transcript_set: TranscriptSet,
    ) -> Dict[str, Any]:
        """Aggregate per-transcript results into group-level results."""
        ...
