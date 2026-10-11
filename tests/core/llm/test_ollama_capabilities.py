"""Unit tests for Ollama /api/show thinking capability parsing."""

from __future__ import annotations

from transcriptx.core.llm.ollama_capabilities import (
    clear_show_cache,
    parse_thinking_controls,
)
from transcriptx.core.llm.thinking_models import resolve_thinking_profile


def test_parse_thinking_controls_with_false() -> None:
    controls = parse_thinking_controls(
        {
            "capabilities": ["completion", "tools", "thinking"],
            "thinking": {"values": [False, True], "default": True},
        }
    )
    assert controls.reports_thinking_capability
    assert controls.can_disable_thinking
    assert controls.has_thinking_object


def test_parse_thinking_controls_levels_only() -> None:
    controls = parse_thinking_controls(
        {
            "capabilities": ["thinking"],
            "thinking": {"values": ["low", "medium", "high"], "default": "medium"},
        }
    )
    assert controls.reports_thinking_capability
    assert not controls.can_disable_thinking


def test_parse_thinking_controls_missing() -> None:
    controls = parse_thinking_controls({"capabilities": ["completion"]})
    assert not controls.reports_thinking_capability
    assert not controls.has_thinking_object
    assert not controls.can_disable_thinking


def test_resolve_thinking_profile_show_disableable(monkeypatch) -> None:
    clear_show_cache()

    def fake_show(model, base_url=None, timeout=5.0):
        return {
            "capabilities": ["thinking"],
            "thinking": {"values": [False, True], "default": True},
        }

    monkeypatch.setattr(
        "transcriptx.core.llm.ollama_capabilities.show_ollama_model", fake_show
    )
    profile = resolve_thinking_profile("qwen3.8:latest", prefer_show=True)
    assert profile.is_thinking
    assert profile.can_disable
    assert profile.source == "show"


def test_resolve_thinking_profile_name_fallback(monkeypatch) -> None:
    clear_show_cache()

    def fake_show(model, base_url=None, timeout=5.0):
        return None

    monkeypatch.setattr(
        "transcriptx.core.llm.ollama_capabilities.show_ollama_model", fake_show
    )
    profile = resolve_thinking_profile("qwen3.8:latest", prefer_show=True)
    assert profile.is_thinking
    assert not profile.can_disable
    assert profile.source == "name"
