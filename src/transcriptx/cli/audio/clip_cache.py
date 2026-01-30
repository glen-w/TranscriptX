"""LRU cache for sliced audio clips."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Optional, Tuple

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import AUDIO_PLAYBACK_CACHE_DIR

logger = get_logger()


class ClipCache:
    """Simple LRU cache for sliced clip files."""

    def __init__(self, max_size: int = 50, cache_dir: Optional[Path] = None) -> None:
        self._max_size = max(1, int(max_size))
        self._cache_dir = Path(cache_dir or AUDIO_PLAYBACK_CACHE_DIR) / "clips"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._entries: OrderedDict[Tuple, Path] = OrderedDict()

    @property
    def cache_dir(self) -> Path:
        return self._cache_dir

    def get_clip(self, key: Tuple) -> Optional[Path]:
        path = self._entries.get(key)
        if path and path.exists():
            self._entries.move_to_end(key)
            return path
        if key in self._entries:
            self._entries.pop(key, None)
        return None

    def put_clip(self, key: Tuple, clip_path: Path) -> None:
        if not clip_path.exists():
            return
        self._entries[key] = clip_path
        self._entries.move_to_end(key)
        self._evict_if_needed()

    def clear_cache(self) -> None:
        for path in list(self._entries.values()):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
        self._entries.clear()

    def _evict_if_needed(self) -> None:
        while len(self._entries) > self._max_size:
            _, path = self._entries.popitem(last=False)
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
