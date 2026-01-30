import json
import os

from geopy.geocoders import Nominatim

CACHE_PATH = os.path.join("data", "cache", "location_cache.json")
geolocator = Nominatim(user_agent="transcriptx")

# Load cache once at module level
if os.path.exists(CACHE_PATH):
    with open(CACHE_PATH) as f:
        location_cache = json.load(f)
else:
    location_cache = {}


def geocode_with_cache(locations: list) -> list:
    """
    Geocode a list of (location_name, count) tuples using cached results.
    Returns list of dicts: {name, lat, lon}
    """
    results = []
    for loc, _ in locations:
        if loc in location_cache:
            results.append(location_cache[loc])
            continue
        try:
            geocoded = geolocator.geocode(loc, timeout=10)
            if geocoded:
                coord = {
                    "name": loc,
                    "lat": geocoded.latitude,
                    "lon": geocoded.longitude,
                }
                location_cache[loc] = coord
                results.append(coord)
        except Exception:
            continue

    # Ensure folder exists before saving cache
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(location_cache, f, indent=2)

    return results
