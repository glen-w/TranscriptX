"""Tests for group chart context fail-closed guards."""

from __future__ import annotations

from transcriptx.core.analysis.group_charts.context_guards import (
    should_emit_cross_session_speaker_charts,
    should_emit_temporal_overlay_charts,
)
from transcriptx.core.analysis.group_charts.registry import (
    GROUP_AGGREGATE_CHART_FAMILIES,
)
from transcriptx.core.pipeline.result_envelope import PerTranscriptResult


def test_temporal_overlay_family_requires_non_empty_ptr() -> None:
    ptr = [
        PerTranscriptResult(
            transcript_path="/a.json",
            transcript_key="k",
            run_id="r",
            order_index=0,
            output_dir="/out",
            module_results={},
        )
    ]
    for agg_id, fam in GROUP_AGGREGATE_CHART_FAMILIES.items():
        if "temporal_overlay" not in fam:
            assert should_emit_temporal_overlay_charts(agg_id, None) is True
            assert should_emit_temporal_overlay_charts(agg_id, []) is True
        else:
            assert should_emit_temporal_overlay_charts(agg_id, None) is False
            assert should_emit_temporal_overlay_charts(agg_id, []) is False
            assert should_emit_temporal_overlay_charts(agg_id, ptr) is True


def test_cross_session_family_requires_canonical_map() -> None:
    class _DummyMap:
        pass

    cmap = _DummyMap()
    for agg_id, fam in GROUP_AGGREGATE_CHART_FAMILIES.items():
        if "cross_session_speaker" not in fam:
            assert should_emit_cross_session_speaker_charts(agg_id, None) is True
            assert should_emit_cross_session_speaker_charts(agg_id, cmap) is True
        else:
            assert should_emit_cross_session_speaker_charts(agg_id, None) is False
            assert should_emit_cross_session_speaker_charts(agg_id, cmap) is True
