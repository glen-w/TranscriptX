"""Shared Folium helpers for location maps.

OpenStreetMap's public ``tile.openstreetmap.org`` CDN blocks many app/embed
clients (HTTP 403 / osm.wiki/Blocked). Folium's default tile layer uses that
CDN, so TranscriptX location maps must opt into a basemap that permits
browser embedding with attribution — CartoDB Positron still shows OSM data
under ODbL via CARTO's CDN.
"""

from __future__ import annotations

from typing import Any, Sequence

# Folium built-in name; resolves to cartodb-basemaps CDN, not tile.openstreetmap.org.
DEFAULT_LOCATION_MAP_TILES = "CartoDB positron"


def create_location_map(
    folium_mod: Any,
    *,
    zoom_start: int = 2,
    location: Sequence[float] | None = None,
) -> Any:
    """Return a Folium map using the default policy-safe basemap."""
    kwargs: dict[str, Any] = {
        "tiles": DEFAULT_LOCATION_MAP_TILES,
        "zoom_start": int(zoom_start),
    }
    if location is not None:
        kwargs["location"] = list(location)
    return folium_mod.Map(**kwargs)
