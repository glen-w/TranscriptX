"""GUI source contracts for Theme E run-time guidance captions."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_run_analysis_wires_guidance() -> None:
    src = Path("src/transcriptx/web/page_modules/run_analysis.py").read_text(
        encoding="utf-8"
    )
    assert "render_run_time_guidance" in src
    assert "run_time_guidance" in src


@pytest.mark.unit
def test_batch_ops_wires_guidance() -> None:
    src = Path("src/transcriptx/web/page_modules/batch_ops.py").read_text(
        encoding="utf-8"
    )
    assert "render_run_time_guidance" in src


@pytest.mark.unit
def test_llm_selector_wires_hardware_hint() -> None:
    src = Path("src/transcriptx/web/components/llm_model_selector.py").read_text(
        encoding="utf-8"
    )
    assert "render_llm_hardware_hint" in src


@pytest.mark.unit
def test_transcribe_audio_wires_stt_recommendation() -> None:
    src = Path("src/transcriptx/web/page_modules/transcribe_audio.py").read_text(
        encoding="utf-8"
    )
    assert "recommend_stt_backend" in src
    assert "probe_hardware" in src


@pytest.mark.unit
def test_guidance_caption_mentions_not_a_promise() -> None:
    from transcriptx.core.observability.hardware_probe import HardwareSnapshot
    from transcriptx.core.observability.run_estimate import (
        estimate_run_wall,
        format_run_time_estimate,
    )
    from transcriptx.core.observability.run_performance.schema import WorkloadSnapshot

    hw = HardwareSnapshot(
        os_family="linux",
        arch="x86_64",
        python_version="3.10.0",
        cpu_count=4,
        cpu_class="low",
        memory_gib=8.0,
        memory_band="mid",
        acceleration="cpu",
        acceleration_reason=None,
        in_container=False,
        install_profile=None,
        force_cpu=False,
    )
    est = estimate_run_wall(
        hardware=hw,
        preset="balanced",
        module_ids=["stats"],
        workload=WorkloadSnapshot(transcript_duration_s=300.0),
    )
    assert "not a promise" in format_run_time_estimate(est).lower()
