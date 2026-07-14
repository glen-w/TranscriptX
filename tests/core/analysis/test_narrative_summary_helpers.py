"""Unit tests for narrative_summary module helpers (no LLM calls)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.core.analysis.narrative_summary import (
    _effective_max_output_tokens,
    _render_narrative_markdown,
)


@pytest.mark.unit
class TestEffectiveMaxOutputTokens:
    def test_explicit_max_tokens_wins(self) -> None:
        client = SimpleNamespace(_max_output_tokens=2048)
        cfg = SimpleNamespace(max_output_tokens=1024)
        assert _effective_max_output_tokens(client, cfg, max_tokens=512) == 512

    def test_client_default_used_when_max_tokens_none(self) -> None:
        client = SimpleNamespace(_max_output_tokens=2048)
        cfg = SimpleNamespace(max_output_tokens=1024)
        assert _effective_max_output_tokens(client, cfg, max_tokens=None) == 2048

    def test_config_fallback_when_client_has_no_default(self) -> None:
        client = SimpleNamespace(_max_output_tokens=None)
        cfg = SimpleNamespace(max_output_tokens=1024)
        assert _effective_max_output_tokens(client, cfg, max_tokens=None) == 1024

    def test_none_when_nothing_configured(self) -> None:
        client = object()
        cfg = SimpleNamespace(max_output_tokens=None)
        assert _effective_max_output_tokens(client, cfg, max_tokens=None) is None


@pytest.mark.unit
class TestRenderNarrativeMarkdown:
    def test_includes_provenance_footer(self) -> None:
        md = _render_narrative_markdown(
            {
                "narrative": "The team discussed things.",
                "provenance": {"prompt_version": "v1", "model": "qwen3:8b"},
            }
        )
        assert md.startswith("# Narrative Summary")
        assert "The team discussed things." in md
        assert "Prompt version: v1" in md
        assert "Model: qwen3:8b" in md

    def test_omits_footer_without_provenance(self) -> None:
        md = _render_narrative_markdown({"narrative": "Text only."})
        assert "---" not in md
        assert "Prompt version" not in md
