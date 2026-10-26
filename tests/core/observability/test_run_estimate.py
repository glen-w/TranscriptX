"""Unit tests for Theme E run-time estimator."""

from __future__ import annotations

import pytest

from transcriptx.core.observability.hardware_probe import HardwareSnapshot
from transcriptx.core.observability.run_estimate import (
    PriorRunTiming,
    estimate_run_wall,
    fingerprint_compatible,
    format_duration_range,
    format_run_time_estimate,
    prior_from_sidecar,
    workload_from_segments,
)
from transcriptx.core.observability.run_performance.schema import (
    RuntimeFingerprint,
    WorkloadSnapshot,
)


def _hw(**overrides) -> HardwareSnapshot:
    base = dict(
        os_family="linux",
        arch="x86_64",
        python_version="3.10.0",
        cpu_count=8,
        cpu_class="mid",
        memory_gib=16.0,
        memory_band="high",
        acceleration="cpu",
        acceleration_reason=None,
        in_container=False,
        install_profile="full",
        force_cpu=False,
    )
    base.update(overrides)
    return HardwareSnapshot(**base)


@pytest.mark.unit
def test_workload_from_segments() -> None:
    segs = [
        {"start": 0.0, "end": 2.0, "speaker": "A", "text": "hello world"},
        {"start": 2.0, "end": 5.5, "speaker": "B", "text": "more words here"},
    ]
    w = workload_from_segments(segs)
    assert w.segment_count == 2
    assert w.speaker_count == 2
    assert w.transcript_duration_s == 5.5
    assert w.word_count == 5


@pytest.mark.unit
def test_quick_faster_than_thorough() -> None:
    hw = _hw()
    modules = ["stats", "summary", "wordclouds"]
    wl = WorkloadSnapshot(transcript_duration_s=1800.0, segment_count=200)
    quick = estimate_run_wall(
        hardware=hw, preset="quick", module_ids=modules, workload=wl
    )
    thorough = estimate_run_wall(
        hardware=hw,
        preset="thorough",
        module_ids=modules + ["chart_descriptions", "llm_summary"],
        workload=wl,
        llm_size_class="mid",
    )
    assert quick.midpoint_s < thorough.midpoint_s
    assert thorough.high_s > quick.high_s


@pytest.mark.unit
def test_llm_increases_estimate() -> None:
    hw = _hw()
    wl = WorkloadSnapshot(transcript_duration_s=1800.0)
    no_llm = estimate_run_wall(
        hardware=hw, preset="balanced", module_ids=["stats", "summary"], workload=wl
    )
    with_llm = estimate_run_wall(
        hardware=hw,
        preset="balanced",
        module_ids=["stats", "summary", "llm_summary", "chart_descriptions"],
        workload=wl,
        llm_size_class="mid",
    )
    assert with_llm.midpoint_s > no_llm.midpoint_s
    assert "llm_modules" in " ".join(with_llm.drivers)


@pytest.mark.unit
def test_missing_workload_low_confidence() -> None:
    est = estimate_run_wall(
        hardware=_hw(),
        preset="balanced",
        module_ids=["stats"],
        workload=None,
    )
    assert est.confidence == "low"
    assert any("duration unknown" in c.lower() for c in est.caveats)


@pytest.mark.unit
def test_calibration_narrows_with_matching_priors() -> None:
    hw = _hw(memory_band="high", acceleration="cpu")
    wl = WorkloadSnapshot(transcript_duration_s=1800.0)
    heuristic = estimate_run_wall(
        hardware=hw,
        preset="balanced",
        module_ids=["stats", "summary"],
        workload=wl,
    )
    priors = [
        PriorRunTiming(
            wall_clock_duration_ms=120_000.0,
            transcript_duration_s=1800.0,
            preset="balanced",
            memory_band="high",
            acceleration="cpu",
        )
    ]
    calibrated = estimate_run_wall(
        hardware=hw,
        preset="balanced",
        module_ids=["stats", "summary"],
        workload=wl,
        priors=priors,
    )
    assert calibrated.confidence == "calibrated"
    # Midpoint should move toward the 120s prior.
    assert abs(calibrated.midpoint_s - 120.0) < abs(heuristic.midpoint_s - 120.0)


@pytest.mark.unit
def test_mismatched_fingerprint_priors_ignored() -> None:
    hw = _hw(memory_band="high", acceleration="cpu")
    wl = WorkloadSnapshot(transcript_duration_s=1800.0)
    priors = [
        PriorRunTiming(
            wall_clock_duration_ms=30_000.0,
            transcript_duration_s=1800.0,
            preset="balanced",
            memory_band="low",
            acceleration="cuda",
        )
    ]
    est = estimate_run_wall(
        hardware=hw,
        preset="balanced",
        module_ids=["stats"],
        workload=wl,
        priors=priors,
    )
    assert est.confidence == "heuristic"


@pytest.mark.unit
def test_group_scales_with_members() -> None:
    hw = _hw()
    wl = WorkloadSnapshot(transcript_duration_s=600.0)
    one = estimate_run_wall(
        hardware=hw,
        preset="balanced",
        module_ids=["stats"],
        workload=wl,
        target_type="transcript",
    )
    group = estimate_run_wall(
        hardware=hw,
        preset="balanced",
        module_ids=["stats"],
        workload=wl,
        target_type="group",
        member_count=3,
    )
    assert group.midpoint_s > one.midpoint_s


@pytest.mark.unit
def test_format_helpers() -> None:
    assert "min" in format_duration_range(480, 900)
    est = estimate_run_wall(
        hardware=_hw(),
        preset="balanced",
        module_ids=["stats"],
        workload=WorkloadSnapshot(transcript_duration_s=600.0),
    )
    text = format_run_time_estimate(est)
    assert "Estimated wall time" in text
    assert "Guidance, not a promise" in text


@pytest.mark.unit
def test_prior_from_sidecar() -> None:
    prior = prior_from_sidecar(
        {
            "wall_clock_duration_ms": 5000,
            "workload": {"transcript_duration_s": 100.0},
            "analysis": {"profile": "balanced", "requested_module_count": 3},
            "runtime_fingerprint": {"memory_band": "mid", "acceleration": "cpu"},
        }
    )
    assert prior is not None
    assert prior.preset == "balanced"
    assert prior.memory_band == "mid"


@pytest.mark.unit
def test_prior_from_sidecar_rejects_invalid_wall() -> None:
    assert prior_from_sidecar({}) is None
    assert prior_from_sidecar({"wall_clock_duration_ms": 0}) is None
    assert prior_from_sidecar({"wall_clock_duration_ms": "nope"}) is None


@pytest.mark.unit
def test_workload_from_segments_empty_and_word_lists() -> None:
    empty = workload_from_segments([])
    assert empty.segment_count == 0
    assert empty.transcript_duration_s == 0.0
    assert empty.word_count == 0
    assert empty.speaker_count == 0

    with_words = workload_from_segments(
        [
            {
                "start": 0.0,
                "end": 1.5,
                "speaker": "A",
                "text": "ignored when words present",
                "words": [{"w": "a"}, {"w": "b"}, {"w": "c"}],
            }
        ]
    )
    assert with_words.word_count == 3
    assert with_words.transcript_duration_s == 1.5


@pytest.mark.unit
def test_format_duration_range_units() -> None:
    assert format_duration_range(30, 45) == "about 30–45s"
    assert format_duration_range(60, 60) == "about 60s"
    assert "h" in format_duration_range(7200, 10800)
    # Mixed units keep both sides explicit.
    mixed = format_duration_range(45, 120)
    assert "s" in mixed and "min" in mixed


@pytest.mark.unit
def test_fingerprint_compatible_matches_memory_and_accel() -> None:
    hw = _hw(memory_band="high", acceleration="cpu")
    assert fingerprint_compatible(None, hw) is False
    assert (
        fingerprint_compatible(
            RuntimeFingerprint(memory_band="mid", acceleration="cpu"), hw
        )
        is False
    )
    assert (
        fingerprint_compatible(
            RuntimeFingerprint(memory_band="high", acceleration="cuda"), hw
        )
        is False
    )
    assert (
        fingerprint_compatible(
            RuntimeFingerprint(memory_band="high", acceleration="cpu"), hw
        )
        is True
    )
    # Empty fingerprint fields are treated as compatible.
    assert fingerprint_compatible(RuntimeFingerprint(), hw) is True


@pytest.mark.unit
def test_container_and_core_install_shape_estimate() -> None:
    wl = WorkloadSnapshot(transcript_duration_s=600.0)
    container = estimate_run_wall(
        hardware=_hw(in_container=True, install_profile="core"),
        preset="balanced",
        module_ids=["stats"],
        workload=wl,
    )
    host_full = estimate_run_wall(
        hardware=_hw(in_container=False, install_profile="full"),
        preset="balanced",
        module_ids=["stats"],
        workload=wl,
    )
    assert any("container" in c.lower() for c in container.caveats)
    assert "install:core" in container.drivers
    assert "install:full" in host_full.drivers
    assert container.midpoint_s < host_full.midpoint_s
