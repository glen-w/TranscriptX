"""Geocoding helper with cache (no network when cache hits)."""

from __future__ import annotations

import pytest


@pytest.mark.unit
def test_geocode_with_cache_uses_memory_cache(monkeypatch, tmp_path) -> None:
    import transcriptx.core.geo_utils as gu

    monkeypatch.setattr(
        gu, "location_cache", {"Paris": {"name": "Paris", "lat": 1.0, "lon": 2.0}}
    )
    monkeypatch.setattr(gu, "CACHE_PATH", tmp_path / "loc_cache.json")
    out = gu.geocode_with_cache([("Paris", 3)])
    assert len(out) == 1
    assert out[0]["lat"] == 1.0
    assert out[0]["lon"] == 2.0
