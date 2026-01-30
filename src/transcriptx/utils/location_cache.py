# src/transcriptx/utils/location_cache.py

import json
import time
from pathlib import Path

from geopy.geocoders import Nominatim

CACHE_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "data"
    / "cache"
    / "location_cache.json"
)

# Global in-memory cache
_location_cache = {}

# Load existing cache from disk if available
if CACHE_PATH.exists():
    try:
        with open(CACHE_PATH) as f:
            _location_cache.update(json.load(f))
    except Exception:
        pass


def geocode_with_cache(locations, user_agent="transcriptx", max_locations=50):
    """
    Geocode a list of (location, count) tuples with caching.
    Returns: list of {"name": loc, "lat": ..., "lon": ...}

    Args:
        locations: List of (location, count) tuples
        user_agent: User agent for geocoding service
        max_locations: Maximum number of locations to geocode (to prevent timeouts)
    """
    geolocator = Nominatim(user_agent=user_agent)
    results = []

    # Sort by count (most frequent first) and limit to max_locations
    sorted_locations = sorted(locations, key=lambda x: x[1], reverse=True)[
        :max_locations
    ]

    for loc, count in sorted_locations:
        if loc in _location_cache:
            coords = _location_cache[loc]
            if coords:
                results.append({"name": loc, **coords})
            continue

        try:
            # Add delay between requests to be respectful to the service
            time.sleep(1)

            location = geolocator.geocode(loc, timeout=10)
            if location:
                coords = {"lat": location.latitude, "lon": location.longitude}
                _location_cache[loc] = coords
                results.append({"name": loc, **coords})
            else:
                _location_cache[loc] = None
        except Exception as e:
            print(f"Geocoding error for '{loc}': {e}")
            _location_cache[loc] = None
            continue

    # Save updated cache to disk
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(_location_cache, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save location cache: {e}")

    return results
