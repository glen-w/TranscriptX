"""
Fail-closed context checks for group chart families.

If an aggregate lists ``temporal_overlay`` or ``cross_session_speaker`` in
``GROUP_AGGREGATE_CHART_FAMILIES``, missing required context must yield **no**
charts of that kind (other chart kinds for the same agg are unaffected).
"""

from __future__ import annotations

from typing import Optional, Sequence

from transcriptx.core.pipeline.result_envelope import PerTranscriptResult
from transcriptx.core.pipeline.speaker_normalizer import CanonicalSpeakerMap


def should_emit_temporal_overlay_charts(
    agg_id: str,
    per_transcript_results: Optional[Sequence[PerTranscriptResult]],
) -> bool:
    from transcriptx.core.analysis.group_charts.registry import (
        GROUP_AGGREGATE_CHART_FAMILIES,
    )

    fam = GROUP_AGGREGATE_CHART_FAMILIES.get(agg_id, ())
    if "temporal_overlay" not in fam:
        return True
    return bool(per_transcript_results)


def should_emit_cross_session_speaker_charts(
    agg_id: str,
    canonical_speaker_map: Optional[CanonicalSpeakerMap],
) -> bool:
    from transcriptx.core.analysis.group_charts.registry import (
        GROUP_AGGREGATE_CHART_FAMILIES,
    )

    fam = GROUP_AGGREGATE_CHART_FAMILIES.get(agg_id, ())
    if "cross_session_speaker" not in fam:
        return True
    return canonical_speaker_map is not None
