"""Unit tests for Theme E analysis model hints."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.llm_support.model_guidance import (
    preferred_size_class_for_memory,
    recommend_llm_for_hardware,
)
from transcriptx.core.observability.backend_recommend import analysis_model_hint
from transcriptx.core.observability.hardware_probe import HardwareSnapshot


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
def test_llm_demotes_large_on_low_ram() -> None:
    assert preferred_size_class_for_memory("low") == "small"
    rec = recommend_llm_for_hardware(
        memory_band="low",
        installed_models=["gemma3:4b", "gemma3:27b", "qwen2.5:7b"],
    )
    assert "gemma3:27b" in rec.demoted_tags
    assert "gemma3:4b" in rec.preferred_tags or "qwen2.5:7b" in rec.preferred_tags
    assert "low" in rec.caption.lower() or "small" in rec.caption.lower()


@pytest.mark.unit
def test_analysis_model_hint_light_on_low_ram() -> None:
    hint = analysis_model_hint(_hw(memory_band="low"), preset="balanced")
    assert hint.prefer_light is True
    assert "MiniLM" in hint.message or "md" in hint.message


@pytest.mark.unit
def test_analysis_model_hint_core_thorough() -> None:
    hint = analysis_model_hint(
        _hw(memory_band="high", install_profile="core"),
        preset="thorough",
    )
    assert "core" in hint.message.lower()
