"""Unit tests for analysis preset resolution offline behaviour."""

from __future__ import annotations

import pytest

from transcriptx.core.analysis.selection import resolve_analysis_preset

pytestmark = [pytest.mark.unit]


def test_quick_preset_excludes_llm_and_heavy_allowlist() -> None:
    """Quick is the offline-friendly UI preset (no LLM / no heavy allowlist)."""
    resolved = resolve_analysis_preset("quick", target="transcript")
    assert resolved.preset == "quick"
    ids = set(resolved.module_ids)
    assert "llm_summary" not in ids
    assert "semantic_similarity" not in ids
    assert "stats" in ids or "echoes" in ids or "politeness" in ids


def test_balanced_default_may_include_llm_summary_allowlist() -> None:
    """Balanced policy allowlists llm_summary (may still filter by suitability)."""
    resolved = resolve_analysis_preset("balanced", target="transcript")
    assert resolved.preset == "balanced"
    # Balanced is the documented UI default; module set is non-empty.
    assert list(resolved.module_ids)
