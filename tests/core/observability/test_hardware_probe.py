"""Unit tests for Theme E hardware probe."""

from __future__ import annotations

import pytest

from transcriptx.core.observability.hardware_probe import (
    clear_hardware_probe_cache,
    cpu_class_from_count,
    detect_acceleration,
    memory_band_from_gib,
    probe_hardware,
)


@pytest.fixture(autouse=True)
def _clear_probe_cache():
    clear_hardware_probe_cache()
    yield
    clear_hardware_probe_cache()


@pytest.mark.unit
def test_memory_band_boundaries() -> None:
    assert memory_band_from_gib(None) == "unknown"
    assert memory_band_from_gib(4.0) == "low"
    assert memory_band_from_gib(8.0) == "mid"
    assert memory_band_from_gib(15.9) == "mid"
    assert memory_band_from_gib(16.0) == "high"
    assert memory_band_from_gib(32.0) == "very_high"
    assert memory_band_from_gib(64.0) == "very_high"


@pytest.mark.unit
def test_cpu_class_from_count() -> None:
    assert cpu_class_from_count(None) == "unknown"
    assert cpu_class_from_count(2) == "low"
    assert cpu_class_from_count(8) == "mid"
    assert cpu_class_from_count(16) == "high"


@pytest.mark.unit
def test_force_cpu_acceleration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_FORCE_CPU", "1")
    accel, reason = detect_acceleration()
    assert accel == "cpu"
    assert reason == "TRANSCRIPTX_FORCE_CPU"


@pytest.mark.unit
def test_probe_hardware_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRANSCRIPTX_FORCE_CPU", raising=False)
    snap = probe_hardware(use_cache=False)
    assert snap.os_family
    assert snap.arch
    assert snap.python_version
    assert snap.memory_band in {"low", "mid", "high", "very_high", "unknown"}
    assert snap.acceleration in {"cpu", "cuda", "mps", "other"}
    fp = snap.to_runtime_fingerprint()
    assert fp.memory_band == snap.memory_band
    assert fp.acceleration == snap.acceleration


@pytest.mark.unit
def test_probe_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSCRIPTX_FORCE_CPU", "1")
    a = probe_hardware(use_cache=True)
    monkeypatch.delenv("TRANSCRIPTX_FORCE_CPU", raising=False)
    b = probe_hardware(use_cache=True)
    assert a is b  # cached
    clear_hardware_probe_cache()
    c = probe_hardware(use_cache=True)
    assert c is not a
