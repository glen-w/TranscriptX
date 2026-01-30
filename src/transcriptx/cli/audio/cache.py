"""PCM cache management for fast segment slicing."""

from __future__ import annotations

import hashlib
import time
import subprocess
from pathlib import Path
from typing import Optional

from transcriptx.core.utils.logger import get_logger
from transcriptx.core.utils.paths import AUDIO_PLAYBACK_CACHE_DIR

from .tools import check_ffmpeg_available, _find_ffmpeg_path

logger = get_logger()


class AudioCacheManager:
    """Manage creation and reuse of PCM working files for audio playback."""

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        self._cache_dir = Path(cache_dir or AUDIO_PLAYBACK_CACHE_DIR)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_or_create_cache(self, audio_path: Path) -> Optional[Path]:
        """Return cached PCM path, creating it if needed."""
        if audio_path is None or not audio_path.exists():
            return None

        cache_key = self._compute_cache_key(audio_path)
        cache_path = self._cache_dir / f"{cache_key}.wav"

        if self.is_cache_valid(cache_path, audio_path):
            return cache_path

        if self.create_pcm_cache(audio_path, cache_path):
            return cache_path

        return None

    def create_pcm_cache(self, audio_path: Path, cache_path: Path) -> bool:
        """Create a 16kHz mono PCM WAV cache file using ffmpeg."""
        ffmpeg_available, ffmpeg_error = check_ffmpeg_available()
        if not ffmpeg_available:
            logger.debug(f"ffmpeg not available for cache: {ffmpeg_error}")
            return False

        ffmpeg_path = _find_ffmpeg_path()
        if not ffmpeg_path:
            logger.debug("ffmpeg path not found for cache creation")
            return False

        cache_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-vn",
            "-sn",
            "-dn",
            "-i",
            str(audio_path),
            "-y",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(cache_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            if result.returncode != 0:
                err = (result.stderr or result.stdout or "Unknown error").strip()
                logger.warning(
                    f"PCM cache creation failed (exit {result.returncode}): {err}"
                )
                if cache_path.exists():
                    try:
                        cache_path.unlink()
                    except OSError:
                        pass
                return False
        except subprocess.TimeoutExpired:
            logger.warning("PCM cache creation timed out")
            if cache_path.exists():
                try:
                    cache_path.unlink()
                except OSError:
                    pass
            return False
        except Exception as exc:
            logger.warning(f"PCM cache creation failed: {exc}")
            if cache_path.exists():
                try:
                    cache_path.unlink()
                except OSError:
                    pass
            return False

        return cache_path.exists() and cache_path.stat().st_size > 0

    def is_cache_valid(self, cache_path: Path, audio_path: Path) -> bool:
        """Validate that cached PCM exists and is newer than source."""
        if not cache_path.exists():
            return False
        try:
            source_mtime = audio_path.stat().st_mtime
            cache_mtime = cache_path.stat().st_mtime
        except OSError:
            return False
        return cache_mtime >= source_mtime

    def cleanup_old_caches(self, max_age_days: int = 30) -> int:
        """Remove cached files older than max_age_days."""
        if max_age_days <= 0:
            return 0
        cutoff = max_age_days * 24 * 60 * 60
        removed = 0
        now = int(time.time())
        for entry in self._cache_dir.glob("*.wav"):
            try:
                age = now - int(entry.stat().st_mtime)
                if age > cutoff:
                    entry.unlink()
                    removed += 1
            except OSError:
                continue
        return removed

    def _compute_cache_key(self, audio_path: Path) -> str:
        """Compute a stable cache key from path, size, and mtime."""
        try:
            stat = audio_path.stat()
            key_source = f"{audio_path.resolve()}|{stat.st_size}|{stat.st_mtime}"
        except OSError:
            key_source = str(audio_path.resolve())
        return hashlib.sha256(key_source.encode("utf-8")).hexdigest()
