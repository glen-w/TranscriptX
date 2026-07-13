"""Tests for lexical diversity utility functions."""

from __future__ import annotations

import math

import pytest

from transcriptx.core.utils.lexical_diversity import (
    MIN_MTLD_TOKENS,
    compute_lexical_diversity_metrics,
    compute_mtld,
    tokenize,
)


@pytest.mark.unit
def test_tokenize_empty() -> None:
    assert tokenize("") == []


@pytest.mark.unit
def test_tokenize_contractions_and_hyphens() -> None:
    tokens = tokenize("Don't state-of-the-art café")
    assert "don't" in tokens
    assert "state-of-the-art" in tokens
    assert "café" in tokens


@pytest.mark.unit
def test_tokenize_excludes_digits_and_underscores() -> None:
    assert tokenize("hello_world v2 42") == ["hello", "world"]


@pytest.mark.unit
def test_empty_text_metrics() -> None:
    metrics = compute_lexical_diversity_metrics("")
    assert metrics["token_count"] == 0
    assert metrics["ttr"] is None
    assert metrics["mtld"] is None
    assert metrics["hapax_rate"] is None


@pytest.mark.unit
def test_single_token_ttr() -> None:
    metrics = compute_lexical_diversity_metrics("hello")
    assert metrics["token_count"] == 1
    assert metrics["type_count"] == 1
    assert metrics["ttr"] == 1.0
    assert metrics["hapax_rate"] == 1.0
    assert metrics["mtld"] is None


@pytest.mark.unit
def test_repeated_tokens_ttr() -> None:
    metrics = compute_lexical_diversity_metrics("hello hello hello")
    assert metrics["token_count"] == 3
    assert metrics["type_count"] == 1
    assert metrics["ttr"] == pytest.approx(1 / 3)


@pytest.mark.unit
def test_mtld_short_stream_null() -> None:
    tokens = tokenize(" ".join(f"word{i}" for i in range(MIN_MTLD_TOKENS - 1)))
    assert compute_mtld(tokens) is None


@pytest.mark.unit
def test_mtld_no_nan() -> None:
    tokens = tokenize(" ".join(["alpha", "beta"] * 40))
    value = compute_mtld(tokens)
    assert value is not None
    assert math.isfinite(value)


@pytest.mark.unit
def test_hapax_rate_denominator_is_type_count() -> None:
    metrics = compute_lexical_diversity_metrics("alpha beta gamma alpha")
    assert metrics["hapax_count"] == 2
    assert metrics["type_count"] == 3
    assert metrics["hapax_rate"] == pytest.approx(2 / 3)
