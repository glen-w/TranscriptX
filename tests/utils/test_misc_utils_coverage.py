"""Tests for misc utils coverage."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from transcriptx.utils import location_cache, simple_progress


@pytest.mark.unit
def test_geocode_with_cache_uses_cache_limits_and_persists(
    tmp_path, monkeypatch, capsys
) -> None:
    calls: list[str] = []

    class FakeGeolocator:
        def __init__(self, user_agent: str) -> None:
            assert user_agent == "tests"

        def geocode(self, loc: str, timeout: int = 10):
            calls.append(loc)
            if loc == "Paris":
                return SimpleNamespace(latitude=48.8566, longitude=2.3522)
            if loc == "Broken":
                raise RuntimeError("boom")
            return None

    cache_path = tmp_path / "location_cache.json"
    monkeypatch.setattr(location_cache, "CACHE_PATH", cache_path)
    monkeypatch.setattr(
        location_cache, "_location_cache", {"Cached": {"lat": 1, "lon": 2}}
    )
    monkeypatch.setattr(location_cache, "Nominatim", FakeGeolocator)
    monkeypatch.setattr(location_cache.time, "sleep", lambda _seconds: None)

    results = location_cache.geocode_with_cache(
        [("Low", 1), ("Paris", 10), ("Cached", 9), ("Broken", 8)],
        user_agent="tests",
        max_locations=3,
    )

    assert results == [
        {"name": "Paris", "lat": 48.8566, "lon": 2.3522},
        {"name": "Cached", "lat": 1, "lon": 2},
    ]
    assert calls == ["Paris", "Broken"]
    assert '"Broken": null' in cache_path.read_text(encoding="utf-8")
    assert "Geocoding error for 'Broken': boom" in capsys.readouterr().out


@pytest.mark.unit
def test_simple_progress_fallback_success_and_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(simple_progress, "YASPIN_AVAILABLE", False)

    with simple_progress.progress("Doing work"):
        pass

    with pytest.raises(ValueError, match="bad"):
        with simple_progress.progress("Failing work"):
            raise ValueError("bad")

    simple_progress.log_progress("step")
    simple_progress.log_warning("careful")
    simple_progress.log_error("nope")
    simple_progress.log_success("done")

    out = capsys.readouterr().out
    assert "Doing work - completed" in out
    assert "Failing work - failed: bad" in out
    assert "step" in out
    assert "careful" in out
    assert "nope" in out
    assert "done" in out
