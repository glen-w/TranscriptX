"""Retired public semantic IDs are stripped (no sibling rewrite)."""

from __future__ import annotations

from transcriptx.core.analysis.selection import filter_modules_by_mode


def test_public_semantic_similarity_survives_filter() -> None:
    out = filter_modules_by_mode(
        ["stats", "semantic_similarity"],
        "full",
    )
    assert "semantic_similarity" in out
    assert "stats" in out


def test_retired_advanced_id_dropped_without_rewrite() -> None:
    out = filter_modules_by_mode(
        ["stats", "semantic_similarity_advanced"],
        "quick",
    )
    assert "semantic_similarity_advanced" not in out
    # Epoch-1: drop only — do not silently reintroduce semantic_similarity.
    assert out == ["stats"]
