"""Context passed into group chart generators."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from transcriptx.core.domain.transcript_set import TranscriptSet
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


@dataclass
class GroupChartContext:
    """Immutable inputs for one group chart generation pass."""

    group_run_root: Path
    group_run_id: str
    agg_id: str
    transcript_set: TranscriptSet
    group_uuid: Optional[str] = None
    per_transcript_results: Optional[List[PerTranscriptResult]] = None
    canonical_speaker_map: Optional[CanonicalSpeakerMap] = None

    @property
    def chart_base_name(self) -> str:
        return self.group_uuid or "group"
