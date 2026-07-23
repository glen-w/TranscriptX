"""Geocoding helper with cache (no network when cache hits)."""

from __future__ import annotations

from types import SimpleNamespace

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


@pytest.mark.unit
def test_geocode_with_cache_miss_and_exception(monkeypatch, tmp_path) -> None:
    import transcriptx.core.geo_utils as gu

    monkeypatch.setattr(gu, "location_cache", {})
    monkeypatch.setattr(gu, "CACHE_PATH", tmp_path / "cache" / "loc.json")

    class _Geo:
        def geocode(self, loc, timeout=10):
            if loc == "Boom":
                raise RuntimeError("network")
            if loc == "Nowhere":
                return None
            return SimpleNamespace(latitude=10.5, longitude=20.5)

    monkeypatch.setattr(gu, "geolocator", _Geo())
    out = gu.geocode_with_cache([("Berlin", 1), ("Boom", 1), ("Nowhere", 1)])
    assert out == [{"name": "Berlin", "lat": 10.5, "lon": 20.5}]
    assert gu.location_cache["Berlin"]["lat"] == 10.5
    assert (tmp_path / "cache" / "loc.json").is_file()
