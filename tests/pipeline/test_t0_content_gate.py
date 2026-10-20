"""Planning/gate check: T0 content modules are not skipped for SPEAKER_00-only."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.pipeline.dag_pipeline_run import speaker_gate_skip_reason
from transcriptx.core.pipeline.module_registry import get_module_info


@pytest.mark.unit
def test_t0_wordclouds_and_quality_not_gated_on_named_count() -> None:
    for mod_id in ("wordclouds", "transcript_quality", "insight_eligibility"):
        info = get_module_info(mod_id)
        assert info is not None, mod_id
        assert (
            speaker_gate_skip_reason(
                info,
                named_speaker_count=0,
                turn_taking_speaker_count=1,
                allow_unnamed_speakers=False,
            )
            is None
        ), mod_id


@pytest.mark.unit
def test_t0_multi_speaker_module_still_skips_on_monologue() -> None:
    info = get_module_info("conversation_loops")
    if info is None:
        info = SimpleNamespace(
            gate_on_turn_taking_speakers=False,
            requires_multiple_speakers=True,
            min_named_speakers=2,
        )
    reason = speaker_gate_skip_reason(
        info,
        named_speaker_count=0,
        turn_taking_speaker_count=1,
        allow_unnamed_speakers=True,
    )
    assert reason is not None
    assert "2" in reason or "multiple" in reason.lower() or "speakers" in reason
