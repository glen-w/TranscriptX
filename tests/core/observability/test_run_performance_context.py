"""Tests for Theme E sidecar context helpers."""

from __future__ import annotations

import pytest

from transcriptx.core.domain.canonical_transcript import CanonicalTranscript
from transcriptx.core.observability.hardware_probe import clear_hardware_probe_cache
from transcriptx.core.observability.run_performance.recorder import (
    RunPerformanceRecorder,
)
from transcriptx.core.observability.run_performance.schema import (
    ExecutionStatus,
    FinalStatus,
)
from transcriptx.core.observability.run_performance_context import (
    build_analysis_context,
    build_runtime_fingerprint,
    build_workload_from_canonical,
)


@pytest.fixture(autouse=True)
def _clear_probe():
    clear_hardware_probe_cache()
    yield
    clear_hardware_probe_cache()


@pytest.mark.unit
def test_build_workload_from_canonical() -> None:
    canonical = CanonicalTranscript.from_segments(
        [
            {"start": 0.0, "end": 10.0, "speaker": "A", "text": "one two"},
            {"start": 10.0, "end": 20.0, "speaker": "B", "text": "three"},
        ]
    )
    wl = build_workload_from_canonical(canonical)
    assert wl is not None
    assert wl.segment_count == 2
    assert wl.speaker_count == 2
    assert wl.transcript_duration_s == 20.0


@pytest.mark.unit
def test_build_analysis_context_uses_preset_from_run_results() -> None:
    ctx = build_analysis_context(
        app_version="0.9.9",
        requested_module_count=4,
        run_results={"analysis_preset": "Balanced", "mode": "full"},
    )
    assert ctx.profile == "balanced"
    assert ctx.mode == "full"
    assert ctx.requested_module_count == 4


@pytest.mark.unit
def test_freeze_persists_fingerprint_and_workload() -> None:
    rec = RunPerformanceRecorder(target_type="transcript", run_id="run-e")
    rec.start_wall_clock()
    rec.stop_wall_clock()
    fp = build_runtime_fingerprint()
    canonical = CanonicalTranscript.from_segments(
        [{"start": 0.0, "end": 5.0, "speaker": "A", "text": "hi"}]
    )
    wl = build_workload_from_canonical(canonical)
    snap = rec.freeze(
        execution_status=ExecutionStatus.succeeded,
        final_status=FinalStatus.succeeded,
        analysis=build_analysis_context(
            app_version="test",
            requested_module_count=1,
            run_results={"analysis_preset": "quick"},
        ),
        workload=wl,
        runtime_fingerprint=fp,
    )
    assert snap.runtime_fingerprint is not None
    assert snap.runtime_fingerprint.memory_band == fp.memory_band
    assert snap.workload is not None
    assert snap.workload.segment_count == 1
    assert snap.analysis is not None
    assert snap.analysis.profile == "quick"
