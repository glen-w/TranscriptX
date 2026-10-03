"""Unit tests for Folium location-map helpers."""

from __future__ import annotations

from typing import Any

import pytest

from transcriptx.core.maps_folium import (
    DEFAULT_LOCATION_MAP_TILES,
    create_location_map,
)


class _FakeMap:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _FakeFolium:
    Map = _FakeMap


@pytest.mark.unit
def test_create_location_map_uses_cartodb_not_osm_default() -> None:
    fmap = create_location_map(_FakeFolium, zoom_start=3, location=[1.0, 2.0])
    assert fmap.kwargs["tiles"] == DEFAULT_LOCATION_MAP_TILES
    assert fmap.kwargs["tiles"] == "CartoDB positron"
    assert fmap.kwargs["zoom_start"] == 3
    assert fmap.kwargs["location"] == [1.0, 2.0]
