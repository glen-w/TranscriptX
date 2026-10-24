"""Unit tests for Theme E STT backend recommendations."""

from __future__ import annotations

import pytest

from transcriptx.core.observability.hardware_probe import HardwareSnapshot
from transcriptx.services.transcription.stt_backend_recommend import (
    recommend_stt_backend,
)


def _hw(**overrides) -> HardwareSnapshot:
    base = dict(
        os_family="linux",
        arch="x86_64",
        python_version="3.10.0",
        cpu_count=8,
        cpu_class="mid",
        memory_gib=8.0,
        memory_band="mid",
        acceleration="cpu",
        acceleration_reason=None,
        in_container=False,
        install_profile="full",
        force_cpu=False,
    )
    base.update(overrides)
    return HardwareSnapshot(**base)


@pytest.mark.unit
def test_stt_prefers_whispermlx_on_darwin() -> None:
    rec = recommend_stt_backend(
        _hw(os_family="darwin"),
        available_provider_ids=["whisperx_docker", "whispermlx"],
    )
    assert rec.provider_id == "whispermlx"
    assert "whispermlx" in rec.caption.lower()


@pytest.mark.unit
def test_stt_cuda_when_visible() -> None:
    rec = recommend_stt_backend(
        _hw(acceleration="cuda"),
        available_provider_ids=["whisperx_docker"],
    )
    assert rec.provider_id == "whisperx_docker"
    assert rec.device == "cuda"


@pytest.mark.unit
def test_stt_cpu_in_container_without_cuda() -> None:
    rec = recommend_stt_backend(
        _hw(acceleration="cpu", in_container=True),
        available_provider_ids=["whisperx_docker", "parakeet_docker"],
    )
    assert rec.device == "cpu"
    assert "container" in rec.caption.lower()


@pytest.mark.unit
def test_stt_force_cpu_overrides_visible_cuda() -> None:
    rec = recommend_stt_backend(
        _hw(acceleration="cuda", force_cpu=True),
        available_provider_ids=["whisperx_docker"],
    )
    assert rec.provider_id == "whisperx_docker"
    assert rec.device == "cpu"
    assert rec.reason == "cpu_fallback"


@pytest.mark.unit
def test_stt_darwin_without_whispermlx_points_at_mlx() -> None:
    rec = recommend_stt_backend(
        _hw(os_family="darwin"),
        available_provider_ids=["whisperx_docker"],
    )
    assert rec.provider_id == "whisperx_docker"
    assert rec.device == "cpu"
    assert "whispermlx" in rec.caption.lower()


@pytest.mark.unit
def test_stt_parakeet_when_whisper_family_absent() -> None:
    cpu = recommend_stt_backend(
        _hw(),
        available_provider_ids=["parakeet_docker"],
    )
    assert cpu.provider_id == "parakeet_docker"
    assert cpu.device == "cpu"
    assert cpu.reason == "parakeet_available"

    cuda = recommend_stt_backend(
        _hw(acceleration="cuda"),
        available_provider_ids=["parakeet_docker"],
    )
    assert cuda.device == "cuda"


@pytest.mark.unit
def test_stt_empty_providers_default_cpu() -> None:
    rec = recommend_stt_backend(_hw(), available_provider_ids=[])
    assert rec.provider_id == "whisperx_docker"
    assert rec.device == "cpu"
    assert rec.reason == "default"
