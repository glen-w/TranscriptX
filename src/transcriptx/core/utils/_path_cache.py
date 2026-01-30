"""
Path resolution cache management for TranscriptX.

This module handles caching of path resolution results to improve performance
when resolving file paths multiple times.
"""

from typing import Dict, Tuple, Any

from transcriptx.core.utils.logger import get_logger

logger = get_logger()

# Path resolution cache
_path_resolution_cache: Dict[Tuple[str, str], Tuple[str, float]] = {}
_cache_ttl = 300  # 5 minutes in seconds
_MAX_CACHE_SIZE = 1000  # Maximum number of cache entries

# Cache statistics
_cache_stats = {"hits": 0, "misses": 0, "evictions": 0}


def _manage_cache_size() -> None:
    """Remove oldest entries if cache exceeds size limit."""
    global _path_resolution_cache, _cache_stats

    if len(_path_resolution_cache) <= _MAX_CACHE_SIZE:
        return

    # Sort by timestamp and remove oldest entries
    sorted_entries = sorted(
        _path_resolution_cache.items(), key=lambda x: x[1][1]  # Sort by timestamp
    )

    # Keep only the most recent MAX_CACHE_SIZE entries
    evicted = len(_path_resolution_cache) - _MAX_CACHE_SIZE
    _path_resolution_cache = dict(sorted_entries[-_MAX_CACHE_SIZE:])
    _cache_stats["evictions"] += evicted
    logger.debug(f"Cache trimmed to {_MAX_CACHE_SIZE} entries (evicted {evicted})")


def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dictionary with cache statistics
    """
    global _path_resolution_cache, _cache_stats

    total_requests = _cache_stats["hits"] + _cache_stats["misses"]
    hit_rate = (
        (_cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0
    )

    return {
        "size": len(_path_resolution_cache),
        "max_size": _MAX_CACHE_SIZE,
        "hits": _cache_stats["hits"],
        "misses": _cache_stats["misses"],
        "hit_rate": f"{hit_rate:.1f}%",
        "evictions": _cache_stats["evictions"],
    }


def invalidate_path_cache(file_path: str | None = None) -> None:
    """
    Invalidate path resolution cache.

    Args:
        file_path: Specific file path to invalidate (if None, clears entire cache)
    """
    global _path_resolution_cache
    if file_path:
        # Remove entries matching this file path
        keys_to_remove = [
            key for key in _path_resolution_cache.keys() if key[0] == file_path
        ]
        for key in keys_to_remove:
            _path_resolution_cache.pop(key, None)
    else:
        # Clear entire cache
        _path_resolution_cache.clear()


# Export cache internals for use by path resolution module
def _get_cache() -> Dict[Tuple[str, str], Tuple[str, float]]:
    """Get the cache dictionary (internal use only)."""
    return _path_resolution_cache


def _get_cache_ttl() -> int:
    """Get the cache TTL (internal use only)."""
    return _cache_ttl


def _get_cache_stats_dict() -> Dict[str, int]:
    """Get the cache stats dictionary (internal use only)."""
    return _cache_stats
