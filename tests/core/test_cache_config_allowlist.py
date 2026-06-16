"""Module cache-affecting config snapshot."""

from __future__ import annotations

import pytest

from transcriptx.core.utils.config import get_config
from transcriptx.core.utils.module_cache_config import get_cache_affecting_config


@pytest.mark.unit
def test_get_cache_affecting_config_sentiment_paths() -> None:
    cfg = get_config()
    payload = get_cache_affecting_config("sentiment", cfg)
    assert "analysis.sentiment_window_size" in payload
    assert "analysis.sentiment_min_confidence" in payload


@pytest.mark.unit
def test_get_cache_affecting_config_stats_empty_allowlist() -> None:
    cfg = get_config()
    assert get_cache_affecting_config("stats", cfg) == {}


@pytest.mark.unit
def test_get_cache_affecting_config_unknown_module_empty() -> None:
    cfg = get_config()
    assert get_cache_affecting_config("not_a_registered_module_id", cfg) == {}
